Title: Reverse engineering the Apple M1 Bluetooth interface
Date: 2023-02-07
Summary: In this post I walk through the thought process as I reverse engineered the M1 Bluetooth module.
Status: draft

Back in April of 2022, I reverse-engineered the interface that drivers use to communicate with the Bluetooth module on Apple M1 machines so that [Asahi Linux](https://asahilinux.org/) could support Bluetooth on these devices. I documented the results in [a prototype driver](https://github.com/ArcaneNibble/m1-bluetooth-prototype) that was written in Python and ran in userspace. By July, other members of the Asahi team had [written a real driver](https://asahilinux.org/2022/07/july-2022-release/) that is now shipping to end users.

In this post, I will document the thought processes that went into this reverse engineering effort. Unfortunately, I experienced a hardware failure in the meantime and don't have my old annotated reverse engineering notes, so this will be done on a best-effort basis.

# Background

Unfortunately, this post cannot be an introduction to reverse engineering as a whole. Reverse engineering is an extremely broad topic with many areas to cover, including

* assembly language and the AArch64 instruction set. The official documentation for the AArch64 instruction set can be found [here](https://developer.arm.com/documentation/102374/0101).
* operating systems. It is extremely useful to have a general idea of how operating systems work and are designed, but, as I will show here, a detailed knowledge of macOS internals is not specifically required. I have gotten away with consulting the [official IOKit documentation](https://developer.apple.com/documentation/iokit) when needed, figuring things out as I go along.
* educated guesswork. _Lots_ of guesswork. Having a vague idea about how other systems work and are designed helps when reverse engineering an unknown system. There are many common patterns (e.g. ring buffers, doorbell registers, firmware loading) that occur throughout different systems, and having this knowledge available to hand makes guessing much faster and more efficient.

# Initial reconnaissance

One of the first things to do when reverse engineering a system is to have a poke around in order to gather information. The first tool I personally reached for was IORegistryExplorer, which is available as part of the "Additional Tools for Xcode." This tool displays information used by macOS device drivers.

The first thing I did was to open IORegistryExplorer, select the IODeviceTree "plane" (I didn't read the documentation enough to know what exactly a plane is, but I did know from previous efforts that this plane matches the Apple Device Tree information that m1n1 can dump), and search for "bluetooth".

![Screenshot of IORegistryExplorer]({static}/images/m1-bt-ioreg-iodt.png)

This immediately tells me some information:

* Bluetooth is running over PCIe. There isn't a standard way of doing this according to the [Bluetooth Core specification](https://www.bluetooth.com/specifications/specs/core-specification-5-3/) (we will need this document again later), but the commands running on top of the PCIe link might still be standard (we do not know yet at this point).
* Bluetooth is a second PCIe function on the same device as WiFi. This can be seen from the `0,1` address (as well as by running `lspci` when booted into Linux).

Repeating the same search on the IOService "plane" results in the following hierarchy:

![Screenshot of IORegistryExplorer]({static}/images/m1-bt-ioreg-ioservice.png)

Some quick research online seems to hint that this may be an Apple-specific interface. At this point, my preference is to jump in to static analysis.

# Static analysis

I began static analysis by loading `AppleBluetoothModule` and `AppleConvergedIPCOLYBTControl` (visible in IORegistryExplorer), as well as the similarly-named `AppleConvergedPCI` as a guess, into [Ghidra](https://ghidra-sre.org/). These drivers can be found inside `/System/Library/Extensions` of a macOS install. Interestingly, when loading these drivers, Ghidra informs us that they are "fat binaries" containing both x86_64 code as well as AArch64 code. It turns out that some of the latest x86 Macs _also_ have a similar Bluetooth module connected over PCIe, and this reverse engineering work has been useful for them as well.

The first thing I do when loading a macOS driver into Ghidra is to look at the class and function names. These are usually not obfuscated and give a good overview of what the code might be doing. Some of the functions in `AppleBluetoothModule` look like this:

![Screenshot of Ghidra with AppleBluetoothModule loaded]({static}/images/m1-bt-applebluetoothmodule.png)

My initial impression was that this code seems to be used for "gluing together random bits related to PCIe" and was not related to "actually talking to the chip," so I quickly moved on to `AppleConvergedPCI` instead:

![Screenshot of Ghidra with AppleConvergedPCI loaded]({static}/images/m1-bt-appleconvergedpci.png)

Ah! At this point I know I'm in the right place because I can see familiar numbers! (It's not visible in the screenshot above, but the device tree in IORegistryExplorer contains a "compatible" string of `wlan-pcie,bcm4387`). One function immediately jumps out to me: `getRegisterOffset`

![Screenshot of getRegisterOffset function]({static}/images/m1-bt-getreg.png)

At this point, we don't yet know what any of these registers do, but the fact that they've been wrapped in this layer of indirection means that most likely either these registers are the _only_ registers the driver accesses or they're at least the _most important_ ones. We can quickly note these down in a "notes" file.

At this point, nothing else in `AppleConvergedPCI` seems to be doing anything particularly interesting, so we move on to `AppleConvergedIPCOLYBTControl`.

![Screenshot of Ghidra with AppleConvergedIPCOLYBTControl loaded]({static}/images/m1-bt-appleconvergedipc.png)

Jackpot? Based on the amount of code in here, as well as the names in IORegistryExplorer, this is almost certainly the bulk of the driver logic. At this point, it's time to perform a bunch of the static analysis Sudoku puzzle. It's hard to describe step-by-step how this process works, but the gist of it is:

1. Find something you don't understand, but where you understand most of the surrounding pieces.
2. Figure out what it does.
3. Repeat until you understand everything.

# Initial static analysis notes

The first thing I noticed was the separate set of classes containing "BTI" vs "RTI". Since I expect that this card probably requires firmware (just like the WiFi function does), I take a wild guess that "BTI" might stand for "boot-time interface" and that "RTI" might stand for "run-time interface". This is backed up by the fact that "BTI" mostly only seems to be able to "send an image" while "RTI" does a lot of work with things like "MR" "CR" "TR" "CD" etc.

When reverse engineering C++, it is _extremely_ helpful to properly define all of the classes in the Ghidra structure editor. In order to figure out the sizes of some of these classes in bytes, I look for calls to the constructor and then look for the preceding calls to `__Znwm` (the global `operator new`):

![Screenshot of Ghidra showing a memory allocation]({static}/images/m1-bt-new.png)

In this case, the size of the `ACIPCBTIPipe` object is 0x30 bytes.

In other cases (mostly classes that are more involved with IOKit), the class itself will contain an `operator new` method that calls into `_OSObject_typed_operator_new`:

![Screenshot of Ghidra showing a memory allocation]({static}/images/m1-bt-osobject-new.png)

Understanding this requires [digging](https://github.com/apple-oss-distributions/xnu/blob/xnu-8020.101.4/osfmk/kern/kalloc.h#L1236) through the XNU source code a bit to find the [size](https://github.com/apple-oss-distributions/xnu/blob/xnu-8020.101.4/osfmk/kern/kalloc.h#L331).

Once a few classes have been briefly annotated, the function of some of the registers starts to become clear. For example, here's a fragment from the `ACIPCBTIDevice::updateImageAddr` method:

![Screenshot of Ghidra showing ACIPCBTIDevice::updateImageAddr]({static}/images/m1-bt-bti-updateimageaddr.png)

The `+ 0x80` and `+ 0x88` vtable calls are `ACIPCControl::writeBar0Register` and `ACIPCControl::writeBar1Register` respectively, which are defined back in the `AppleConvergedPCI` driver (I do not know a convenient way to annotate vtables in Ghidra and usually follow them manually). This shows that the BTI "image" (which we are guessing is firmware, but have not yet confirmed) address is written to registers 0x19/0x20 and 3/4. Some further reverse engineering following the same reasoning finally yields an initial register list like in [this commit](https://github.com/ArcaneNibble/m1n1/commit/7f0cc2700686534bd26f72000b29847a05924943).

Finally, various "debug" and "state dump" functions often provide useful hints, such as this method `ACIPCRTIDevice::stateDump`:

![Screenshot of Ghidra showing ACIPCRTIDevice::stateDump]({static}/images/m1-bt-statedump.png)

However, at this point in time, it is not 100% clear exactly what a lot of these RTI-related structures do, and it eventually becomes easier to supplement static analysis with dynamic analysis.

# Switching to tracing and dynamic analysis

In order to switch to dynamic analysis and trace what macOS is doing, we make use of m1n1's hypervisor. When this effort was first being performed, there was no code to help with tracing PCIe devices, so I wrote a tracer that hard-codes the physical addresses that the Bluetooth device PCIe BARs get mapped to. This was "good enough" to get initial reverse engineering done.

By dumping the "image" that is initially sent to the card (code [here](https://github.com/ArcaneNibble/m1n1/commit/a5089dae08f785ee30b01f24fbd28de75d9d9413)) and then comparing it against files in `/usr/share/firmware/bluetooth`, we can confirm that this first stage is indeed a firmware load done by the "BTI" classes. We can also dump the "context" set by `ACIPCRTIDevice::updateContextAddr` and confirm that it matches the structure printed by `ACIPCRTIDevice::stateDump` (this code is [here](https://github.com/ArcaneNibble/m1n1/commit/23e8c240f72b9a6d8c5921f2a7a8a7deb7038704)).

![Screenshot of Bluetooth context structure]({static}/images/m1-bt-ctx.png)

At this point, a very tedious back-and-forth process occurs of updating the tracer based on static analysis findings, and then updating the static analysis based on the tracer results. The first significant milestone is uncovering the ring buffer used for control messages on pipe 0 (code [here](https://github.com/ArcaneNibble/m1n1/commit/fff333341cb5e14803805127ae7895cdb27da3ff)).

![Screenshot of Bluetooth control pipe message]({static}/images/m1-bt-pipe0-msg.png)

The tedious back-and-forth repeats again, but I start noticing that a lot of the settings that go into these control messages seem to come from Somewhere™ that I don't understand. Eventually, in a flash of insight, I open `/System/Library/Extensions/AppleConvergedIPCOLYBTControl.kext/Contents/Info.plist` and discover:

![Screenshot of Info.plist]({static}/images/m1-bt-infoplist.png)

... oh. Sometimes it helps to read the documentation. Reading through this plist file, we discover that it references separate pipes for "HCI", "SCO", "ACL", and "debug". I don't know what any of these terms are, but a quick poke through the Bluetooth Core specification reveals this table when describing the UART transport layer

![Screenshot of Bluetooth specification UART packet indicators]({static}/images/m1-bt-uartspec.png)

This is starting to make sense. Instead of adding a byte prefix like the UART transport layer, Apple seems to have separated out each type of Bluetooth packet into a separate "pipe" with its own ring buffers, and the plist specifies how these are all tied together.

The reverse engineering process proceeds until the tracer can [dump HCI commands](https://github.com/ArcaneNibble/m1n1/commit/709be6644289b33596271cdd7f2c9af52e076b9e) as well as [their corresponding responses](https://github.com/ArcaneNibble/m1n1/commit/40abf193e90079b0d04b9d9cb22cff87b718dab9). This finally results in [this Tweet](https://twitter.com/ArcaneNibble/status/1513129726516232192) showing command 0x1002 `Read_Local_Supported_Commands` in the TR and the corresponding reply in the CR. From the dumps, we can confirm that this Bluetooth adapter _does_ indeed still use standard HCI commands, just wrapped in this Apple-specific transport.

At this point, we can also make reasonable guesses as to what various abbreviations in the driver codebase mean:

* HIA - head index A?
* TIA - tail index A?
* CR - completion ring
* TR - transfer ring
* MR - message/management ring
* TD - transfer descriptor
* CD - completion descriptor

It's time to be brave and try driving the device ourselves with our own driver!

# Prototyping a new driver

In order to prototype a driver quickly, I wanted to be able to use a high-level programming language that's extremely convenient for rapid prototyping, such as Python. Most of the other Asahi experimentation is already done with Python scripts running on a separate PC interfacing with m1n1. However, there weren't any examples of how to set up a PCIe device under m1n1, and I didn't want to invest a lot of effort into making that work. Fortunately, Linux already has functionality for writing userspace PCIe drivers — [VFIO](https://docs.kernel.org/driver-api/vfio.html). VFIO is well-known for allowing "passthrough" of PCIe devices from a hypervisor host to virtual machines, but it also allows safe (IOMMU-protected) access to PCIe devices from userspace.

I start putting together a Python skeleton to poke BAR registers interactively while booted into Linux. However, I quickly discover an issue — accessing some registers (e.g. `CHIPCOMMON_CHIP_STATUS`) works, but accessing most registers cause _the entire machine_ to lock up and eventually watchdog reboot. This happens even if I access them in the exact same sequence as macOS does. Much frustration ensues.

Eventually, I start using the debugging technique of "what information do I have that I have _not_ used yet?" One obvious piece of information is the `AppleConvergedPCI` driver and the `ACIPCChip43XX` classes, all of which seem to just initialize some magic numbers and then not do anything else. While thoroughly combing through this driver (and continuing to bang my head against the desk), I eventually notice `AppleConvergedPCI::setupVendorSpecificConfigGated`

![Screenshot of Ghidra showing AppleConvergedPCI::setupVendorSpecificConfigGated]({static}/images/m1-bt-configspace.png)

PCIe config space. Of course. Since the PCIe configuration space is not part of a BAR, none of my tracing captured any of it. It's also the perfect location to put magic pokes that completely change how the rest of the chip behaves. This also explains what the magic numbers in `ACIPCChip43XX` are for — they are written into the configuration space to change what is mapped into the memory BARs. This also explains why not setting them up causes a system lockup — accessing an invalid/unmapped address. Pasting these pokes into my Python driver and... success! I can read/write registers without crashing. From there, it's a [very quick bit of code](https://github.com/ArcaneNibble/m1-bluetooth-prototype/commit/5c243d6077ed3ab7ecc8c6f5cfb27b81b9899c3f) until I can successfully boot the firmware.

Once the firmware is booted, I just need to set up the RTI "context" data structure, and then I can transition the firmware into state 1 followed by state 2 where it should be running (code [here](https://github.com/ArcaneNibble/m1-bluetooth-prototype/commit/2a2e5d26e4a93cb2ca5706cfa5797596459e8d49)).

From here, further iteration and experimentation gets to the point where [completion rings can be opened](https://github.com/ArcaneNibble/m1-bluetooth-prototype/commit/637d90c02706e378e085d924826f3e8ef2de57ba) followed by [opening transfer rings](https://github.com/ArcaneNibble/m1-bluetooth-prototype/commit/2327dd357ea5626e5827bd786a4061df58b8caeb). At this point, we can now manually send Bluetooth HCI commands via the Python interactive shell.

The macOS kernel driver does not handle higher-level concerns such as calibration (deferring these to userspace). However, in order to make this work under Linux, we have to do this functionality ourselves. The m1n1 tracer is now complete enough to show that the relevant commands are 0xFD97 to load calibration and 0xFE0D to load a "PTB" (both within the vendor-specific command range). In the prototype, we duplicate the commands [here](https://github.com/ArcaneNibble/m1-bluetooth-prototype/commit/8d29ac95260a65f90c892d62a5095b7f6ba37b2f). At this point, I can finally send 0x0C1A `Write_Scan_Enable` via the Python interactive shell and get [this Tweet](https://twitter.com/ArcaneNibble/status/1513463982073409537) where an Android phone is detecting the M1.

# Fleshing out the prototype driver

After getting HCI commands working via an interactive shell, the next logical step is to try to integrate it with the rest of the Linux Bluetooth stack. Fortunately, Linux once again has a good mechanism for doing this — [Bluetooth VHCI](https://github.com/torvalds/linux/blob/master/drivers/bluetooth/hci_vhci.c). There doesn't appear to be any documentation about how this is supposed to work, but the interface happens to be straightforward enough (open `/dev/vhci` and then read/write packets prefixed by a byte indicating HCI packet type).

Quickly hooking this together yielded [this Tweet](https://twitter.com/ArcaneNibble/status/1513478297740406785) showing the M1 laptop scanning and detecting an Android phone, with everything already correctly plumbed through all the way to the GUI layer.

At this point, I attempt to support SCO data, but it uses a different doorbell mechanism and immediately causes an interrupt storm. I set this aside and decide to come back to it later (this is always a valid approach). I instead decide to tackle ACL data, which requires me to figure out how the sharing of completion rings works. I try to test using command 0x1802 `Write_Loopback_Mode`, only to discover that it appears to be broken or otherwise somehow crashes the firmware. Undeterred, I decided to just plow forwards and integrate ACL experiments directly into the existing VHCI logic.

While experimenting with this, I compared against multiple traces I had captured from macOS and eventually discovered the following major quirk: when ACL data to the host fits inside the completion ring, the buffer passed in the transfer ring is not used. The buffer in the transfer ring is only used when the data is too large to fit directly inside the completion ring. (There are flag bits in the descriptor that indicate this.) Once this was [correctly handled](https://github.com/ArcaneNibble/m1-bluetooth-prototype/commit/3d282b88e1a606c60723ea398b20635d5028d048), I posted [this Tweet](https://twitter.com/ArcaneNibble/status/1513804983308746753) where I successfully sent a file via OBEX to a phone.

However, it was clear that there was still a bug. [Implementing](https://github.com/ArcaneNibble/m1-bluetooth-prototype/commit/2c9ffc71b84f88c02db3c8391c3425d46aed31e5) analogous handling of larger ACL buffers going out to the adapter was sufficient to finally fix that as well (after resetting multiple pieces of software repeatedly as they got confused by bogus data). With that, pairing and playing audio via A2DP [worked](https://twitter.com/ArcaneNibble/status/1513820969902608384)!

Finally, I re-enabled the SCO logic I had set aside (and ignored the resulting interrupt storm). This appeared to _also_ work, so I declared the prototype "complete enough," wrote a README, and announced it publicly.

# Aftermath

Eventually, sven from the Asahi project took on the effort needed to turn this prototype into a real driver. For the most part, this was a fairly straightforward affair. However, some further discoveries were made along the way:

* several of the unknown register writes (e.g. `REG_21` and `REG_24`) in my prototype can just be ignored with seemingly no effect
* treating the SCO doorbell as... not special causes the interrupt storm problem to go away
* the details of reading the chip ID, revision, and OTP were figured out in order to select the correct firmware
* the adapters [use reserved bits to indicate the channel of received BLE advertisements](https://lore.kernel.org/asahi/166786921601.3686.4643669436357800810.git-patchwork-notify@kernel.org/T/#mb9a33cacfc9c3ba9b604240335c1fe2cba1f1d46). This helps explain why BLE did not work in my testing with my prototype.
* quirks specific to the 4377 and 4378 chips were figured out

But, with all of that sorted, the driver has made its way upstream!
