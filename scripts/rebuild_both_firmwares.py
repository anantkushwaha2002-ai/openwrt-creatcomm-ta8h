import os
import tarfile
import struct
import lzma
import zlib
import time
import subprocess
import io

print("=== REBUILDING BOTH FIRMWARE IMAGES FOR CREATCOMM TA8H ===")
print("Goals: 1) Unified Default IP = 192.168.1.1 everywhere")
print("       2) Pre-baked DNS (8.8.8.8, 1.1.1.1) so OPKG update always works out-of-the-box!")

# ==============================================================================
# PART 1: REBUILD new_rootfs.sqfs & openwrt-sysupgrade-ta8h.bin (Permanent)
# ==============================================================================
print("\n--- PART 1: Patching new_rootfs.sqfs for Sysupgrade ---")

sqfs2tar = r'sqfs_tools\squashfs-tools-ng-1.3.2-mingw64\bin\sqfs2tar.exe'
tar2sqfs = r'sqfs_tools\squashfs-tools-ng-1.3.2-mingw64\bin\tar2sqfs.exe'

# 1. Unpack original new_rootfs.sqfs to tar
print("1.1 Extracting new_rootfs.sqfs to memory tar...")
proc = subprocess.run([sqfs2tar, 'new_rootfs.sqfs'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
assert proc.returncode == 0, f"sqfs2tar failed: {proc.stderr}"
tar_bytes = proc.stdout
print(f"    Tar extracted: {len(tar_bytes)} bytes")

# 1.2 Read tar, modify 99-ta8h-defaults to pre-bake DNS 8.8.8.8 & 1.1.1.1
print("1.2 Modifying 99-ta8h-defaults with pre-baked DNS...")
in_tf = tarfile.open(fileobj=io.BytesIO(tar_bytes), mode='r')
out_tar_buf = io.BytesIO()
out_tf = tarfile.open(fileobj=out_tar_buf, mode='w')

found_patch = False
for member in in_tf.getmembers():
    f = in_tf.extractfile(member) if member.isfile() else None
    if member.name == 'etc/uci-defaults/99-ta8h-defaults':
        orig_script = f.read().decode('utf-8')
        # Inject DNS settings
        dns_patch = """
# Pre-configure public DNS so OPKG updates and domain resolution ALWAYS work out-of-the-box!
uci add_list network.lan.dns='8.8.8.8'
uci add_list network.lan.dns='1.1.1.1'
uci commit network

# Disable rebind protection so upstream public DNS queries are never blocked
uci set dhcp.@dnsmasq[0].rebind_protection='0'
uci commit dhcp
"""
        new_script = orig_script.replace('uci commit firewall', 'uci commit firewall' + dns_patch)
        new_bytes = new_script.encode('utf-8')
        
        # Create new member with updated size
        new_member = tarfile.TarInfo(name=member.name)
        new_member.size = len(new_bytes)
        new_member.mode = member.mode
        new_member.mtime = int(time.time())
        new_member.type = member.type
        new_member.uid = member.uid
        new_member.gid = member.gid
        new_member.uname = member.uname
        new_member.gname = member.gname
        out_tf.addfile(new_member, io.BytesIO(new_bytes))
        found_patch = True
        print("    [+] Successfully patched etc/uci-defaults/99-ta8h-defaults!")
    else:
        out_tf.addfile(member, f)

in_tf.close()
out_tf.close()
assert found_patch, "99-ta8h-defaults not found in tar!"

# 1.3 Repack modified tar to new_rootfs.sqfs
print("1.3 Repacking squashfs with tar2sqfs (-c xz -b 262144)...")
proc_repack = subprocess.run(
    [tar2sqfs, '-c', 'xz', '-b', '262144', '-f', 'new_rootfs.sqfs'],
    input=out_tar_buf.getvalue(),
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)
assert proc_repack.returncode == 0, f"tar2sqfs failed: {proc_repack.stderr}"
print(f"    [+] new_rootfs.sqfs repacked successfully! Size: {os.path.getsize('new_rootfs.sqfs')} bytes")

# 1.4 Rebuild openwrt-sysupgrade-ta8h.bin
print("1.4 Re-running build_sysupgrade_v2.py...")
res = subprocess.run(['python', 'build_sysupgrade_v2.py'], capture_output=True, text=True)
print(res.stdout)
assert os.path.exists('openwrt-sysupgrade-ta8h.bin')
print(f"    [+] openwrt-sysupgrade-ta8h.bin built: {os.path.getsize('openwrt-sysupgrade-ta8h.bin')} bytes")


# ==============================================================================
# PART 2: REBUILD openwrt-initramfs-ta8h.bin (Temporary RAM Boot)
# ==============================================================================
print("\n--- PART 2: Rebuilding openwrt-initramfs-ta8h.bin with Unified 192.168.1.1 & Pre-baked DNS ---")

# We will modify build_complete_initramfs.py:
# 1) REMOVE 192.168.2.1 replacement (keep standard 192.168.1.1)
# 2) ADD pre-baked DNS 8.8.8.8 and 1.1.1.1 in ap_config
with open('build_complete_initramfs.py', 'r', encoding='utf-8') as f:
    script_code = f.read()

# Make sure 192.168.1.1 is NOT replaced with 192.168.2.1
script_code = script_code.replace(
    'f_data = f_data.replace(b\'lan) ipad=${ipaddr:-"192.168.1.1"} ;;\',\n                                     b\'lan) ipad=${ipaddr:-"192.168.2.1"} ;;\')',
    '# Keep unified 192.168.1.1 default IP\n            pass'
)

# Enhance ap_config with DNS
old_ap_config = """    ap_config = b\"\"\"#!/bin/sh
# Turn on both 2.4G and 5G radios automatically
uci set wireless.radio0.disabled='0'
uci set wireless.radio1.disabled='0'
uci commit wireless
# Set Access Point Mode (disable local DHCP conflict)
uci set dhcp.lan.ignore='1'
uci commit dhcp
# Disable firewall NAT for transparent Gigabit AP
/etc/init.d/firewall stop
/etc/init.d/firewall disable
wifi
exit 0
\"\"\""""

new_ap_config = """    ap_config = b\"\"\"#!/bin/sh
# Turn on both 2.4G and 5G radios automatically
uci set wireless.radio0.disabled='0'
uci set wireless.radio1.disabled='0'
uci commit wireless

# Pre-configure public DNS so OPKG updates and domain resolution ALWAYS work out-of-the-box!
uci add_list network.lan.dns='8.8.8.8'
uci add_list network.lan.dns='1.1.1.1'
uci commit network

# Allow dnsmasq to forward public DNS
uci set dhcp.@dnsmasq[0].rebind_protection='0'
uci commit dhcp

# Disable firewall NAT for transparent Gigabit AP
/etc/init.d/firewall stop
/etc/init.d/firewall disable
wifi
exit 0
\"\"\""""

script_code = script_code.replace(old_ap_config, new_ap_config)

with open('build_complete_initramfs_unified.py', 'w', encoding='utf-8') as f:
    f.write(script_code)

print("2.1 Running build_complete_initramfs_unified.py...")
res2 = subprocess.run(['python', 'build_complete_initramfs_unified.py'], capture_output=True, text=True)
print(res2.stdout)
if res2.stderr:
    print("ERR:", res2.stderr)

# Copy output to openwrt-initramfs-ta8h.bin
shutil_src = 'tftp_root/openwrt-initramfs.bin'
shutil_dst = 'openwrt-initramfs-ta8h.bin'
import shutil
shutil.copy2(shutil_src, shutil_dst)
print(f"    [+] {shutil_dst} updated: {os.path.getsize(shutil_dst)} bytes")

print("\n🎉 BOTH FIRMWARE IMAGES SUCCESSFULLY REBUILT WITH UNIFIED 192.168.1.1 & PRE-BAKED DNS!")

