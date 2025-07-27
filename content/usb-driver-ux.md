Title: Making USB widgets easy to install
Date: 2025-07-27
Summary: Extra descriptors for Windows and WebUSB
Status: draft

# TL;DR

Set `bcdDevice` to `0x0210`, add [this](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/microsoft-os-2-0-descriptors-specification) and optionally [this](https://developer.chrome.com/docs/capabilities/build-for-webusb).

# What? (Historical context)

When hardware is added to a computer, the computer needs to know how to talk to this hardware. In order to be able to, the computer relies on some software _drivers_.

Nowadays, many users no longer have to think about this thanks to the availability of _standards_ which allow for generic drivers to interface with _any_ hardware that operates according to the rules of the standard. Many of these generic drivers now come bundled with the system and don't have to be manually installed.

The USB standard defines both a basic set of rules that all USB devices need to follow as well as a list of standard "[device classes](https://www.usb.org/defined-class-codes)" for commonly-encountered peripherals (such as mice, keyboards, flash drives, cameras, or more specialized things such as smart cards or electronics test and measurement lab equipment).

As stated, nowadays almost any standard mouse or keyboard or flash drive from any manufacturer will work on any computer or even many mobile devices because they all follow the same specification. But what happens if you want to do something other than what is standard and generic? Custom software and occasionally custom drivers are still required.

For example, you often need custom software and sometimes custom drivers to make "Gamer Pro X RGB+ Ultra" keyboards and mice work properly or to configure their advanced settings.

## Not-Windows

On macOS and Linux, the operating system provides a way for programs (in user-space) to talk to USB devices "without a driver" (i.e. by only relying on the basic behaviors that all USB devices must implement). This user-space program essentially takes the place of a driver. For devices which do not need to provide services to the entire system, this interface is sufficient.

For example, a device which only needs to receive a firmware update or configuration settings can use just these basic low-level USB operations. So can a specialized piece of industrial equipment which only talks to its special control software. However, something such as a network card would not fit this model nearly as well because it needs to be accessible and shared by every program on the computer _as a network card_.

## Windows

Unfortunately, the above is not the case on Windows. Windows requires _every_ USB device to have a driver before a user-space program is able to access it.

Double-unfortunately, developing drivers is generally considered difficult since drivers operate in a totally different environment from "normal" user-space programs. Many people thus reasonably want to avoid doing it. In addition, it is not possible to develop a Windows driver without spending money and going through [a lot of bureaucratic red tape](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/kernel-mode-code-signing-requirements--windows-vista-and-later-). This is because Microsoft at some point both wanted to improve their [reputation](https://www.youtube.com/watch?v=IW7Rqwwth84) for instability as well as generally [locking down the platform](https://en.wikipedia.org/wiki/Trustworthy_computing).

People naturally looked for solutions and workarounds to these problems.

## Corporate slop solution&mdash;Jungo WinDriver

Jungo WinDriver is a commercial package sold to companies so that they can quickly develop custom drivers with minimal effort.

As a <abbr title="business-to-business">B2B</abbr> vendor, the only time someone would notice the existence of Jungo is when a company is being particularly low-effort with their driver development.

A number of vendors of "industrial" development kits, equipment, and other such items fell into this category.

## USB <abbr title="Human Interface Device">HID</abbr> workaround

One of the generic device classes with built-in drivers on most platforms (including Windows) is the USB Human Interface Device class. This device class encompasses keyboards, mice, joysticks, gamepads, and other similar widgets.

Because this specification was being designed in the 1990s when many wacky ideas were still being thrown around by computer peripheral manufacturers (i.e. before everybody standardized around an Xbox-style gamepad), this specification is defined in an extremely-generic way (that is simultaneously both excessive and unnecessary in some areas and short-sighted and limiting in others).

Although the devices listed are primarily thought of as _input_ devices, many of them have limited _output_ capabilities as well. For example, traditional PC keyboards have LEDs for Caps Lock, Num Lock, and Scroll Lock, all of which are controllable in software. Joysticks and gamepads also support force feedback (another overcomplicated specification which is almost impossible to understand).

Because of the extensibility of USB HID, it is possible to add vendor-specific commands to HID devices, and none of the major platforms require writing a custom driver to interface with them. This is a reasonable way to implement a computer peripheral that needs some extra blinkenlights.

However, because of how generic USB HID is, it's possible to push it to the extreme and define a device where the _entirety_ of its input and output "reports" consists solely of "vendor defined", up to the limit of the USB packet size. This entirely defeats the spirit of the specification but results in a simple bidirectional channel with a USB device.

An upside of this strategy is that it is _extremely_ backwards-compatible. The Windows HID API is available all the way back to Windows 2000, and the macOS HID API appears to be present since the earliest versions of Mac OS X. Downsides include somewhat limited performance and inflexible programming interfaces (since it is designed for input devices and is *not* a general-purpose USB interface).

## Open-source generic drivers

Over the years, a number of open-source generic USB drivers for Windows were released, including [libusb-win32](https://github.com/mcuee/libusb-win32), [libusbK](https://github.com/mcuee/libusbk), and [usbdk](https://github.com/daynix/UsbDk). These drivers attempt to bring to Windows a similar interface as is available on macOS and Linux (i.e. the ability to write user-space programs to talk to a device, with the driver relying on only generic USB functionality).

These drivers all have slightly different capabilities and different bugs. They also require installation as they do not come preinstalled on the system. The process of installing a specific driver for a specific device was initially rather cumbersome and prompted the release of [tools](https://zadig.akeo.ie/) to simplify the process (tools which *also* needed to be downloaded).

# WinUSB

Because this was a sufficiently visible issue (industrial customers and <abbr title="independent hardware vendors">IHVs</abbr>, including lazy IHVs, are an important part of the ecosystem which Microsoft depends on), Microsoft also developed their own generic USB driver called WinUSB. It has existed since Vista but has been backported to Windows XP.

Because this driver is developed by Microsoft, Microsoft is responsible for maintaining it and distributing it (either via Windows Update or by being included in the operating system starting with Windows 8).

A problem with both the open-source generic USB drivers and this WinUSB generic driver is that there was no way to specify using only standard USB descriptors that generic drivers should be loaded. Normally, driver loading is controlled by combinations of the USB vendor ID, product ID, and device class. However, generic drivers can potentially be associated with _any_ vendor or product.

The way Microsoft decided to solve this problem was by either requiring a special metadata (`.inf`) file to be installed by the end-user, or by requiring the device to implement special "Microsoft OS Descriptors" in the device's firmware.

# Microsoft OS Descriptors

There are two versions of Microsoft OS Descriptors, [version 1.0](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/microsoft-os-1-0-descriptors-specification) and [version 2.0](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/microsoft-os-2-0-descriptors-specification). Version 1.0 is supported since Windows XP SP1 while version 2.0 is supported since Windows 8.1.

These descriptors can be used to tell Windows explicitly to load a certain driver (such as WinUSB), as well as to give devices a <abbr title="Globally Unique Identifier">GUID</abbr>, which is important for some reason that I don't currently understand. These descriptors can also allegedly configure other settings such as the icon which is displayed in Device Manager, but I was not able to figure out how to actually do this.

The most important thing is that, with these descriptors, _driver installation becomes entirely automatic and seamless_, even for devices which implement completely custom USB functionality.

This is not a code-focused article, but [here](https://github.com/pybricks/pybricks-micropython/blob/1808d73d581d85477df702787d6543ff6bf6c131/lib/pbio/drv/usb/usb_common_desc.c#L36-L60) is an example of a Microsoft OS 2.0 Descriptor which requests that Windows load the WinUSB driver.

Microsoft OS 1.0 Descriptors should also work and should enable even greater compatibility, but there seems to be much less interest in continuing to support it. <small>(Personal speculation: this may be due to the aggressive push to roll out Windows 10 as well as some of these WinUSB capabilities seemingly being [pushed for or at least associated with Windows Phone efforts](https://libusb-devel.narkive.com/kNFnzBoL/microsoft-has-apparently-enabled-winusb-wcid-for-windows-7-through-windows-update))</small>

## USB Binary Object Store

The USB Binary Object Store (BOS) descriptor is a mechanism for a USB device to describe "extra" structured binary data for a host. This data is "extra" in the sense that it is not required to operate the core USB device framework. This is, once again like many aspects of USB, excessively generic.

This descriptor originated with some combination of the Wireless USB specification (which has since been memory-holed) and the USB 3.0 specification. It was then backported so that it can also be used with USB 2.0 devices. To use them, devices which are aware of BOS descriptors must report a `bcdDevice` in the device descriptor of at least 2.0.1 or 2.1.0 depending on which "extra" features are indicated.

Examples of "extra" capabilities described by BOS descriptors include Wireless USB data rates and capabilities, support for USB 2.0 Link Power Management (the original reason for the backport), and information about USB 3 speeds and power management latencies.

One of the categories of "extra" capabilities is a capability for defining platform-specific capabilities (identified by a GUID).

A specific GUID, `{D8DD60DF-4589-4CC7-9CD2-659D9E648A9F}`, is used to indicate support for Microsoft OS Descriptors 2.0. An example can be seen [here](https://github.com/pybricks/pybricks-micropython/blob/1808d73d581d85477df702787d6543ff6bf6c131/lib/pbio/drv/usb/usb_common_desc.c#L82-L94).

# WebUSB

Due to ecosystem trends which were very much intentional but out of scope for this article, a lot of software nowadays is delivered through Chromium-based web browsers. As part of enabling web browsers to become a major software delivery channel, the [WebUSB](https://developer.mozilla.org/en-US/docs/Web/API/WebUSB_API) API was introduced to allow web pages to talk to USB devices using the generic USB device framework described throughout this article.

A device which is _intended_ to be accessed from a website can embed a URL inside its firmware by adding a special [WebUSB descriptor](https://developer.chrome.com/docs/capabilities/build-for-webusb). This is optional, but having one will enable browsers to automatically offer to open the specified web page. This means that the end-to-end user experience for a device becomes "plug in device, driver automatically installs, browser automatically offers to open a page containing software to use the device".

WebUSB support is also indicated in the USB BOS descriptor using a platform GUID of `{3408b638-09a9-47a0-8bfd-a0768815b665}`.

# Conclusion

This future certainly is weird, and compatibility and platform-specific issues spill out into becoming everybody's problem, but there finally exists _a_ way to make drivers less painful. You "just" need to know how.

Now you know!
