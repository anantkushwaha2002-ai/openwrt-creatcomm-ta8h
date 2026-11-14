import struct
import lzma
import zlib
import time
import os

def build_sysupgrade():
    print("=== Building Permanent Zero-Touch Sysupgrade Firmware for CreatComm TA8H ===")
    
    # 1. Load generic vmlinux from yuncore_xd3200-sysupgrade.bin
    print("1. Extracting vmlinux kernel from yuncore_xd3200-sysupgrade.bin...")
    orig_sys = open('yuncore_xd3200-sysupgrade.bin', 'rb').read()
    
    uimage_hdr = orig_sys[:64]
    kernel_size = struct.unpack('>I', uimage_hdr[12:16])[0]
    kernel_comp = orig_sys[64:64+kernel_size]
    
    # Decompress LZMA kernel
    raw_kernel = lzma.decompress(kernel_comp, format=lzma.FORMAT_ALONE)
    dtb_pos = raw_kernel.find(b'\xd0\x0d\xfe\xed')
    assert dtb_pos != -1, "DTB magic not found"
    clean_vmlinux = raw_kernel[:dtb_pos]
    print(f"   Clean generic vmlinux size: {len(clean_vmlinux)} bytes ({hex(len(clean_vmlinux))})")
    
    # 2. Append CreatComm TA8H DTB
    print("2. Appending custom CreatComm TA8H DTB...")
    ta8h_dtb = open('creatcomm_ta8h_generated.dtb', 'rb').read()
    print(f"   TA8H DTB size: {len(ta8h_dtb)} bytes")
    
    combined_kernel = clean_vmlinux + ta8h_dtb
    uncomp_len = len(combined_kernel)
    
    # 3. Compress kernel with LZMA
    print("3. Compressing kernel with OpenWrt LZMA...")
    filters = [{'id': lzma.FILTER_LZMA1, 'dict_size': 8388608, 'lc': 1, 'lp': 2, 'pb': 2}]
    compressed = lzma.compress(combined_kernel, format=lzma.FORMAT_ALONE, filters=filters)
    comp_kernel = compressed[:5] + uncomp_len.to_bytes(8, 'little') + compressed[13:]
    comp_len = len(comp_kernel)
    print(f"   Compressed kernel size: {comp_len} bytes")
    
    # 4. Create uImage header
    print("4. Generating uImage header for kernel...")
    uimage_magic = 0x27051956
    load_addr    = 0x80060000
    entry_point  = 0x80060000
    epoch_time   = int(time.time())
    img_name     = b"MIPS OpenWrt Linux-5.15.167"
    
    data_crc = zlib.crc32(comp_kernel) & 0xffffffff
    header_nobc = struct.pack(
        ">IIIIIIIBBBB32s",
        uimage_magic, 0, epoch_time, comp_len, load_addr, entry_point,
        data_crc, 5, 5, 2, 3, img_name
    )
    header_crc = zlib.crc32(header_nobc) & 0xffffffff
    uimage_header = struct.pack(
        ">IIIIIIIBBBB32s",
        uimage_magic, header_crc, epoch_time, comp_len, load_addr, entry_point,
        data_crc, 5, 5, 2, 3, img_name
    )
    
    kernel_uimage = uimage_header + comp_kernel
    
    # Pad kernel to 64KB boundary (0x240000)
    pad_target = 0x240000
    if len(kernel_uimage) > pad_target:
        pad_target = ((len(kernel_uimage) + 0xffff) // 0x10000) * 0x10000
    kernel_padded = kernel_uimage + b'\x00' * (pad_target - len(kernel_uimage))
    print(f"   Kernel padded to {hex(pad_target)} ({len(kernel_padded)} bytes)")
    
    # 5. Load customized new_rootfs.sqfs
    print("5. Loading customized rootfs with baked-in AP settings & 02_network...")
    new_sqfs = open('new_rootfs.sqfs', 'rb').read()
    assert new_sqfs[:4] == b'hsqs', "Squashfs magic hsqs not found"
    
    # Pad squashfs with 0xFF to next 64KB boundary
    sqfs_len = len(new_sqfs)
    sqfs_pad_target = ((sqfs_len + 0xffff) // 0x10000) * 0x10000
    pad_bytes = b'\xff' * (sqfs_pad_target - sqfs_len)
    sqfs_padded = new_sqfs + pad_bytes
    print(f"   Squashfs padded from {sqfs_len} to {len(sqfs_padded)} bytes ({hex(len(sqfs_padded))})")
    
    # 6. Load verified fwtool metadata trailer
    if os.path.exists('ta8h_verified_trailer.bin'):
        trailer = open('ta8h_verified_trailer.bin', 'rb').read()
        print(f"   Loaded verified fwtool metadata trailer ({len(trailer)} bytes)")
    else:
        old_sqfs_and_trailer = orig_sys[0x240000:]
        deadcode_pos = old_sqfs_and_trailer.find(b'\xde\xad\xc0\xde')
        assert deadcode_pos != -1, "DEADCODE marker not found"
        trailer = bytearray(old_sqfs_and_trailer[deadcode_pos:])
        dev_pos = trailer.find(b'yuncore,xd3200')
        if dev_pos != -1:
            trailer[dev_pos:dev_pos+14] = b'creatcomm,ta8h'
        board_pos = trailer.find(b'yuncore_xd3200')
        if board_pos != -1:
            trailer[board_pos:board_pos+14] = b'creatcomm_ta8h'
        
    # 7. Assemble final sysupgrade binary
    final_image = kernel_padded + sqfs_padded + bytes(trailer)
    print(f"7. Total Sysupgrade Image size: {len(final_image)} bytes ({len(final_image)/(1024*1024):.2f} MB)")
    
    out_file = 'openwrt-sysupgrade-ta8h.bin'
    with open(out_file, 'wb') as f:
        f.write(final_image)
    print(f"\n>>> SUCCESS: {out_file} built successfully! <<<")
    
    # Also copy to tftp_root for convenience
    tftp_file = os.path.join('tftp_root', out_file)
    with open(tftp_file, 'wb') as f:
        f.write(final_image)
    print(f">>> Copied to {tftp_file} <<<")

if __name__ == '__main__':
    build_sysupgrade()

