# CreatComm Technology TA8H OpenWrt 23.05.5 by Anant Kushwaha

[![Firmware Version](https://img.shields.io/badge/OpenWrt-23.05.5-blue.svg)](https://openwrt.org/)
[![SoC](https://img.shields.io/badge/SoC-Qualcomm%20Atheros%20QCA9558-red.svg)](https://www.qualcomm.com/)
[![Switch](https://img.shields.io/badge/Switch-Atheros%20AR8337%20Gigabit-orange.svg)](https://openwrt.org/)
[![MIMO](https://img.shields.io/badge/Wireless-2x2%20MIMO%20Dual--Band-blue.svg)](https://openwrt.org/)
[![Maintainer](https://img.shields.io/badge/Customization-Anant%20Kushwaha-green.svg)](https://github.com/anantkushwaha2002-ai)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An optimized, fully modernized OpenWrt 23.05.5 (Linux Kernel 5.15 LTS / `ath79` Device Tree) firmware build for the **CreatComm Technology TA8H** high-power outdoor wireless access point. Customized and maintained by **Anant Kushwaha**.

This release cleanly transitions the board from the obsolete **`ar71xx`** target (LEDE 17.01.4 / Linux 4.4) to the modern, mainline **`ath79/generic`** architecture with full LuCI, working OPKG package feeds, and stable dual-band Wi-Fi.

---

## 📋 Hardware Specifications

<table>
<tr>
<td width="55%" valign="top">

| Component | Specification |
| :--- | :--- |
| **Model / Board** | CreatComm Technology TA8H (`creatcomm,ta8h`) |
| **SoC** | Qualcomm Atheros QCA9558 ver 1 rev 0 @ 720 MHz |
| **CPU Architecture** | MIPS 74Kc (32-bit Big-Endian, `mips_24kc`) |
| **RAM** | 128 MB DDR2 (2x Winbond DRAM @ 600 MHz) |
| **Flash** | 16 MB Winbond SPI-NOR Flash (`w25q128`) |
| **Gigabit Switch** | Qualcomm Atheros AR8337 Rev 2 (Dual CPU RGMII/SGMII) |
| **Wireless 2.4 GHz** | SoC internal `ath9k` **2x2 MIMO** 802.11b/g/n (up to 300 Mbps, 27 dBm) |
| **Wireless 5 GHz** | PCIe `ath10k` QCA9880 / QCA9882 **2x2 MIMO** 802.11ac (up to 867 Mbps, 30 dBm) |
| **Ethernet Ports** | 2x Gigabit Ethernet (1x LAN, 1x WAN with 48V PoE-In) |
| **Power** | 12V DC Jack or 48V Active / Passive PoE |

</td>
<td width="45%" align="center" valign="middle">

<img src="images/creatcomm_ta8h_board.jpg" alt="CreatComm TA8H PCB Board" width="100%" style="border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.15);" />
<br />
<em>CreatComm Technology TA8H Hardware Board</em>

</td>
</tr>
</table>

---

## 🚀 Key Highlights

* **Modern ath79 Device Tree Architecture**:
  * Upgrades the obsolete 2017 `ar71xx` build (Linux 4.4) to modern OpenWrt 23.05.5 (Linux 5.15.167 LTS).
  * Native Device Tree (`dts`) bindings with accurate switch pad delays (`pad0_cfg = 0x03000101`, `pad6_cfg = 0x4a000000`) for wire-speed Gigabit routing.
* **Dual-Band 2x2 MIMO High-Power Wireless**:
  * **5 GHz AC**: Pre-configured `OpenWrt_5G` on Channel 44 (80 MHz VHT80, 30 dBm / 1 Watt transmit power) powered by `ath10k-ct`.
  * **2.4 GHz N**: Pre-configured `OpenWrt_2.4G` on Channel 1 (40 MHz HT40, 27 dBm / 500 mW transmit power) powered by `ath9k`.
* **Verified Official OPKG Software Feeds**:
  * Connected directly to official `downloads.openwrt.org/releases/23.05.5/` feeds with valid signature verification.
  * `luci-app-opkg` pre-installed for 1-click package management in the LuCI web interface.
* **Hardware & ART Partition Safety**:
  * Firmware size (~6.06 MB) safely fits within the 15.6 MB partition.
  * Completely protects factory RF calibration data and MAC addresses in the **ART partition** (`0x00ff0000 - 0x01000000`).

---

## 📥 Firmware Downloads

| Firmware File | Description | Size | Download Link |
| :--- | :--- | :--- | :--- |
| **`openwrt-sysupgrade-ta8h.bin`** | Permanent Sysupgrade Firmware Image | ~6.06 MB | [📥 Download Sysupgrade (.bin)](https://github.com/anantkushwaha2002-ai/openwrt-creatcomm-ta8h/releases/download/v1.0.0/openwrt-sysupgrade-ta8h.bin) |
| **`openwrt-initramfs-ta8h.bin`** | Safe RAM Test Firmware (Zero Flash Writes) | ~5.38 MB | [📥 Download Initramfs (.bin)](https://github.com/anantkushwaha2002-ai/openwrt-creatcomm-ta8h/releases/download/v1.0.0/openwrt-initramfs-ta8h.bin) |

---

## 🛠️ Step-by-Step Installation Guide

> [!IMPORTANT]
> **Why Browser Upload From Old Firmware Fails:**  
> The original firmware (MAKSAT Meshmax / LEDE 17.01) runs on the legacy **`ar71xx`** platform. If you try to upload modern **`ath79`** images directly in the old LuCI web browser interface, it will reject the image with an *"Image verification failed"* or *"Unsupported format"* warning due to the target architecture transition. Follow either **Method 1** (Recommended & Safest) or **Method 2** below.

### Method 1: Safe RAM Boot via TFTP (Recommended / Zero Risk)
This method boots OpenWrt purely inside the 128 MB DDR2 RAM without writing a single byte to the flash chip:

1. Download **`openwrt-initramfs-ta8h.bin`** and place it in your TFTP server folder (e.g. Tftpd64).
2. Set your PC's Ethernet IPv4 address to:
   * **IP Address**: `192.168.1.10`
   * **Subnet Mask**: `255.255.255.0`
   * **Gateway**: `192.168.1.1`
3. Connect an Ethernet cable from your PC to the router's LAN port.
4. Connect a USB-to-UART TTL serial adapter (115200 baud, 8N1) to the router header.
5. Power on the board and press any key to enter the **U-Boot** prompt (`ath> `).
6. Run the following commands (using the verified high-memory address **`0x82000000`** to prevent memory overwrite):
   ```bash
   setenv ipaddr 192.168.1.1
   setenv serverip 192.168.1.10
   tftpboot 0x82000000 openwrt-initramfs-ta8h.bin
   bootm 0x82000000
   ```
7. **Accessing the RAM System**:
   * The RAM temporary build is pre-configured with IP **`192.168.2.1`** (to prevent subnet conflicts with existing home routers).
   * Set your PC to `192.168.2.10` (or obtain IP automatically via DHCP).
   * Open your web browser at: **`http://192.168.2.1/`** (LuCI WebUI).
8. **Permanent Flashing from RAM**:
   * In LuCI, go to **System -> Backup / Flash Firmware**.
   * Upload **`openwrt-sysupgrade-ta8h.bin`**.
   * **Uncheck** "Keep settings" and click **Flash**!

---

### Method 2: Direct CLI Sysupgrade via SSH (Without Opening the Case)
If you already have SSH access to your original router on its existing IP (e.g. `192.168.10.2`):

1. Copy the sysupgrade binary to the router's `/tmp` directory using SCP:
   ```bash
   scp openwrt-sysupgrade-ta8h.bin root@192.168.10.2:/tmp/
   ```
2. Log in via SSH:
   ```bash
   ssh root@192.168.10.2
   ```
3. Run `sysupgrade` with the force (`-F`) and clean (`-n`) flags:
   ```bash
   sysupgrade -F -n /tmp/openwrt-sysupgrade-ta8h.bin
   ```
   *Explanation: `-F` overrides the target architecture check between `ar71xx` and `ath79`, and `-n` discards outdated 2017 settings to prevent crashes.*
4. Wait 2-3 minutes for the device to flash and reboot.

---

## 🌐 Post-Installation IP Addresses & OPKG Configuration

### Default IP Addressing
* **Temporary RAM Boot Build**: **`192.168.2.1`** (avoids subnet clash with upstream routers).
* **Permanent Flash Build**: **`192.168.1.1`** (standard OpenWrt default IP).
* **Default Credentials**: Username `root`, No password by default.

### ⚠️ How to Avoid OPKG DNS Lookup Errors
When configuring this board as an Access Point (Dumb AP) with a static IP (e.g. `192.168.10.11`):
1. Navigate in LuCI to **Network -> Interfaces -> LAN -> Edit**.
2. Set your static **IPv4 Address** (e.g. `192.168.10.11`) and **IPv4 Netmask** (`255.255.255.0`).
3. **CRITICAL**: Set **IPv4 Gateway** to your main upstream router (e.g. `192.168.10.1`).
4. **CRITICAL**: Add **Use custom DNS servers** (e.g. `8.8.8.8` and `192.168.10.1`).
5. Save & Apply.

> [!TIP]
> If Gateway or DNS are omitted on a static LAN interface, running `opkg update` will fail with:  
> `wget: bad address 'downloads.openwrt.org'`  
> As long as Gateway and DNS are configured, `opkg update` and package downloads succeed 100%!

---

## 👤 Author & Credits

* **Firmware Customization, Optimization & Maintenance**: **Anant Kushwaha**
* **Upstream Base**: [OpenWrt Project](https://openwrt.org/) (`ath79/generic`) & CreatComm Technology Co., Ltd.
* **License**: Released under the permissive **[MIT License](LICENSE)** — free for anyone to use, modify, and distribute.
