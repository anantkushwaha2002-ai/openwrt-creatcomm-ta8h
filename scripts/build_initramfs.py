import os
import tarfile
import struct
import lzma
import zlib
import time

def build_allinone():
    print("=== Building Verified Complete Initramfs for CreatComm TA8H ===")
    
    # 1. Load original generic base kernel
    print("1. Loading base kernel from sophos_ap100-initramfs.bin...")
    orig_uimage = open('sophos_ap100-initramfs.bin', 'rb').read()
    raw = bytearray(lzma.decompress(orig_uimage[64:], format=lzma.FORMAT_ALONE)[:0x153c0a0])
    
    cpio_start = 0x777080
    cpio_end   = 0x153bfbc
    target_len = cpio_end - cpio_start
    print(f"   Target CPIO slot: {hex(cpio_start)} to {hex(cpio_end)} ({target_len} bytes)")
    
    # 2. Parse CPIO entries
    print("2. Parsing base CPIO archive...")
    cpio_data = raw[cpio_start:cpio_end]
    offset = 0
    entries = []
    while offset < len(cpio_data):
        if cpio_data[offset:offset+6] != b'070701':
            break
        hdr = cpio_data[offset:offset+110]
        namesize = int(hdr[94:102], 16)
        filesize = int(hdr[54:62], 16)
        mode = int(hdr[14:22], 16)
        ino = int(hdr[6:14], 16)
        uid = int(hdr[22:30], 16)
        gid = int(hdr[30:38], 16)
        nlink = int(hdr[38:46], 16)
        mtime = int(hdr[46:54], 16)
        name_offset = offset + 110
        name = cpio_data[name_offset:name_offset+namesize-1].decode('latin1')
        file_offset = (name_offset + namesize + 3) & ~3
        file_data = cpio_data[file_offset:file_offset+filesize]
        offset = (file_offset + filesize + 3) & ~3
        if name == 'TRAILER!!!':
            break
        entries.append((ino, mode, uid, gid, nlink, mtime, name, file_data))
        
    print(f"   Parsed {len(entries)} base entries.")
    
    # 3. Filter unneeded PPP, CA-cert, and nf_tables files (not needed for AP bridge)
    remove_prefixes = [
        'usr/sbin/pppd',
        'etc/ssl/certs/ca-certificates',
        'usr/lib/pppd',
        'lib/modules/5.15.167/ppp',
        'lib/netifd/proto/ppp',
        'lib/netifd/ppp',
        'etc/ppp',
        'etc/modules.d/ppp',
        'lib/modules/5.15.167/nf_tables.ko'
    ]
    filtered = [e for e in entries if not any(e[6].startswith(p) for p in remove_prefixes)]
    print(f"   Filtered out {len(entries) - len(filtered)} unneeded files.")
    
    # 4. Extract 5G modules and firmware
    print("4. Extracting 5G kernel modules and firmware...")
    ipk_dir = 'packages_5g'
    extra_files = {}
    
    def extract_from_ipk(ipk_name):
        path = os.path.join(ipk_dir, ipk_name)
        with tarfile.open(path, 'r:gz') as t:
            data_tar = t.extractfile('./data.tar.gz')
            with tarfile.open(fileobj=data_tar, mode='r:gz') as dt:
                for m in dt.getmembers():
                    if m.isfile():
                        extra_files[m.name.lstrip('./')] = dt.extractfile(m).read()
                        
    extract_from_ipk('kmod-ath10k_5.15.167+6.1.110-1-1_mips_24kc.ipk')
    extract_from_ipk('ath10k-firmware-qca988x_20230804-1_mips_24kc.ipk')
    extract_from_ipk('ath10k-board-qca988x_20230804-1_mips_24kc.ipk')
    
    ap_config = b"""#!/bin/sh
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
"""
    extra_files['etc/uci-defaults/99-ta8h-ap-config'] = ap_config
    
    # Update network switch config in config_generate and 02_network
    updated = []
    max_ino = max(e[0] for e in filtered) + 1
    cur_time = int(time.time())
    
    for ino, mode, uid, gid, nlink, mtime, name, f_data in filtered:
        if name == 'bin/config_generate':
            # Keep unified 192.168.1.1 default IP
            pass
        elif name == 'etc/board.d/02_network':
            target2 = b'\t\t;;\n\tairtight,c-75)\n\t\tucidef_add_switch "switch0" \\\n\t\t\t"0@eth0" "2:wan" "3:lan" "6@eth1"'
            repl2   = b'\t\t;;\ncreatcomm,ta8h)\n\t\tucidef_add_switch "switch0" \\\n\t\t\t"0@eth0" "2:lan" "3:lan" "6@eth1"'
            f_data = f_data.replace(target2, repl2)
        updated.append((ino, mode, uid, gid, nlink, mtime, name, f_data))
        
    dirs_to_add = [
        'lib/firmware/ath10k',
        'lib/firmware/ath10k/QCA988X',
        'lib/firmware/ath10k/QCA988X/hw2.0'
    ]
    for d in dirs_to_add:
        updated.append((max_ino, 0o40755, 0, 0, 2, cur_time, d, b''))
        max_ino += 1
        
    for fpath, fdata in extra_files.items():
        mode = 0o100755 if fpath.endswith(('.ko', 'ap-config')) or 'bin' in fpath else 0o100644
        updated.append((max_ino, mode, 0, 0, 1, cur_time, fpath, fdata))
        max_ino += 1
        
    updated.append((0, 0, 0, 0, 1, 0, 'TRAILER!!!', b''))
    
    # 5. Pack CPIO
    print("5. Packing CPIO archive...")
    cpio_buf = bytearray()
    for ino, mode, uid, gid, nlink, mtime, name, file_data in updated:
        name_b = name.encode('latin1') + b'\x00'
        namesize = len(name_b)
        filesize = len(file_data)
        hdr = f'070701{ino:08X}{mode:08X}{uid:08X}{gid:08X}{nlink:08X}{mtime:08X}{filesize:08X}00000003000000010000000000000000{namesize:08X}00000000'.encode('ascii')
        cpio_buf.extend(hdr)
        cpio_buf.extend(name_b)
        while len(cpio_buf) % 4 != 0: cpio_buf.append(0)
        cpio_buf.extend(file_data)
        while len(cpio_buf) % 4 != 0: cpio_buf.append(0)
        
    print(f"   New CPIO size: {len(cpio_buf)} bytes (target slot: {target_len} bytes)")
    assert len(cpio_buf) <= target_len, "CPIO exceeds target_len!"
    
    # Pad CPIO with zeros up to EXACTLY target_len
    padding_needed = target_len - len(cpio_buf)
    cpio_padded = cpio_buf + b'\x00' * padding_needed
    assert len(cpio_padded) == target_len
    print(f"   Padded CPIO with {padding_needed} null bytes to exactly fit slot {hex(cpio_start)} - {hex(cpio_end)}")
    
    # 6. Reconstruct raw kernel with exact DTB offset
    print("6. Assembling kernel with exact DTB alignment at 0x153c0a0...")
    raw[cpio_start:cpio_end] = cpio_padded
    
    # Append DTB
    dtb_data = open('creatcomm_ta8h_generated.dtb', 'rb').read()
    assert dtb_data[:4] == b'\xd0\x0d\xfe\xed', "DTB magic invalid"
    
    uncompressed_payload = bytes(raw) + dtb_data
    uncomp_len = len(uncompressed_payload)
    print(f"   Total uncompressed payload: {uncomp_len} bytes ({hex(uncomp_len)})")
    
    # Check that DTB magic is at EXACTLY 0x153c0a0
    dtb_offset = uncompressed_payload.find(b'\xd0\x0d\xfe\xed')
    print(f"   DTB magic located at: {hex(dtb_offset)} (EXPECTED: 0x153c0a0)")
    assert dtb_offset == 0x153c0a0, f"DTB offset mismatch: {hex(dtb_offset)} != 0x153c0a0"
    
    # 7. Compress with OpenWrt LZMA
    print("7. Compressing with OpenWrt LZMA...")
    filters = [{'id': lzma.FILTER_LZMA1, 'dict_size': 8388608, 'lc': 1, 'lp': 2, 'pb': 2}]
    compressed = lzma.compress(uncompressed_payload, format=lzma.FORMAT_ALONE, filters=filters)
    compressed_payload = compressed[:5] + uncomp_len.to_bytes(8, 'little') + compressed[13:]
    comp_len = len(compressed_payload)
    print(f"   Compressed payload size: {comp_len} bytes")
    
    # 8. Create uImage header
    uimage_magic = 0x27051956
    load_addr    = 0x80060000
    entry_point  = 0x80060000
    epoch_time   = int(time.time())
    img_name     = b"MIPS OpenWrt Linux-5.15.167"
    
    data_crc = zlib.crc32(compressed_payload) & 0xffffffff
    header_nobc = struct.pack(
        ">IIIIIIIBBBB32s",
        uimage_magic, 0, epoch_time, comp_len, load_addr, entry_point,
        data_crc, 2, 5, 2, 3, img_name
    )
    header_crc = zlib.crc32(header_nobc) & 0xffffffff
    uimage_header = struct.pack(
        ">IIIIIIIBBBB32s",
        uimage_magic, header_crc, epoch_time, comp_len, load_addr, entry_point,
        data_crc, 2, 5, 2, 3, img_name
    )
    
    final_image = uimage_header + compressed_payload
    
    out_paths = [
        'openwrt-initramfs-ta8h-allinone.bin',
        'tftp_root/openwrt-initramfs.bin',
        'tftp_root/a.bin'
    ]
    for p in out_paths:
        with open(p, 'wb') as f:
            f.write(final_image)
        print(f"   Saved -> {p} ({len(final_image)} bytes)")
        
    print("\nSUCCESS! Perfectly aligned All-in-One image ready for RAM boot!")

if __name__ == '__main__':
    build_allinone()
