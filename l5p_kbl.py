#!/usr/bin/env python

#
# Lenovo Legion 5 Pro 2021 keyboard light controller
# Shara, 2021, MIT
#
# Add udev rule as "/etc/udev/rules.d/10-kblight.rules" if you want control light as user
# SUBSYSTEM=="usb", ATTR{idVendor}=="048d", ATTR{idProduct}=="c965", MODE="0666"
#
# Payload description
#
# HEADER ........... cc
# HEADER ........... 16
# EFFECT ........... 01 - static / 03 - breath / 04 - wave / 06 - hue
# SPEED ............ 01 / 02 / 03 / 04
# BRIGHTNESS ....... 01 / 02
# RED SECTION 1 .... 00-ff
# GREEN SECTION 1 .. 00-ff
# BLUE SECTION 1 ... 00-ff
# RED SECTION 2 .... 00-ff
# GREEN SECTION 2 .. 00-ff
# BLUE SECTION 2 ... 00-ff
# RED SECTION 3 .... 00-ff
# GREEN SECTION 3 .. 00-ff
# BLUE SECTION 3 ... 00-ff
# RED SECTION 4 .... 00-ff
# GREEN SECTION 4 .. 00-ff
# BLUE SECTION 4 ... 00-ff
# UNUSED ........... 00
# WAVE MODE RTL .... 00 / 01
# WAVE MODE LTR .... 00 / 01
# UNUSED ........... 00
# UNUSED ........... 00
# UNUSED ........... 00
# UNUSED ........... 00
# UNUSED ........... 00
# UNUSED ........... 00
# UNUSED ........... 00
# UNUSED ........... 00
# UNUSED ........... 00
# UNUSED ........... 00
# UNUSED ........... 00
# UNUSED ........... 00
# UNUSED ........... 00
#

import re

import usb.core


class LedController:
    # Keyboard light device
    # Integrated Technology Express, Inc. ITE Device(8295)
    VENDOR = 0x048D
    PRODUCT = 0xC965
    EFFECT = {"static": 1, "breath": 3, "wave": 4, "hue": 6}

    def __init__(self):
        device = usb.core.find(idVendor=self.VENDOR, idProduct=self.PRODUCT)

        if device is None:
            raise ValueError("Light device not found")

        # Prevent usb.core.USBError: [Errno 16] Resource busy
        if device.is_kernel_driver_active(0):
            device.detach_kernel_driver(0)

        self.device = device

    # Build light device control string
    def build_control_string(
        self,
        effect,
        colors=None,
        speed=1,
        brightness=1,
        wave_direction=None,
    ):
        data = [204, 22]

        if effect == "off":
            data.append(self.EFFECT["static"])
            data += [0] * 30
            return data

        data.append(self.EFFECT[effect])
        data.append(speed)
        data.append(brightness)

        if effect not in ["static", "breath"]:
            data += [0] * 12
        else:
            chunk = None
            for section in range(0, 4):

                if section < len(colors):
                    color = colors[section].lower()

                    model = None
                    # Detect color model
                    if re.match(r"^[0-9a-f]{6}$", color):
                        # HEX model
                        chunk = [
                            int(color[i : i + 2], 16) for i in range(0, len(color), 2)
                        ]
                    else:
                        components = color.split(",")

                        if components[0].isdigit():
                            # RGB model
                            components = list(map(lambda c: int(c), components))

                            # Validate RGB input
                            for component in components:
                                if not 0 <= component <= 255:
                                    raise ValueError(
                                        f"Invalid RGB color model: {color}"
                                    )

                            chunk = list(components)

                        elif re.match(r"^\d+\.\d+$", components[0]):
                            # HSV model
                            components = list(map(lambda c: float(c), components))

                            # Validate HSV input
                            for component in components:
                                if not 0 <= component <= 1:
                                    raise ValueError(
                                        f"Invalid HSV color model: {color}"
                                    )

                            from colorsys import hsv_to_rgb

                            chunk = list(
                                map(lambda c: int(c * 255), hsv_to_rgb(*components))
                            )

                        else:
                            raise ValueError(f"Invalid color model: {color}")

                data += chunk

        # Unused
        data += [0]

        # Wave direction
        if wave_direction == "rtl":
            data += [1, 0]
        elif wave_direction == "ltr":
            data += [0, 1]
        else:
            data += [0, 0]

        # Unused
        data += [0] * 13

        return data

    # Send command to device
    def send_control_string(self, data):
        self.device.ctrl_transfer(
            bmRequestType=0x21,
            bRequest=0x9,
            wValue=0x03CC,
            wIndex=0x00,
            data_or_wLength=data,
        )


# CLI Stuff
if __name__ == "__main__":
    import argparse

    # Parse arguments
    argparser = argparse.ArgumentParser(
        description="Lenovo Legion 5 Pro 2021 keyboard light controller"
    )

    effect_subparsers = argparser.add_subparsers(help="Light effect", dest="effect")

    # Global options
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument(
        "--brightness",
        type=int,
        choices=range(1, 3),
        default=1,
        help="Light brightness",
    )

    # Options for custom color settings only
    custom_parser = argparse.ArgumentParser(add_help=False)
    custom_parser.add_argument("colors", nargs="+", help="Colors of sections")

    # Options for wave effect
    wave_parser = argparse.ArgumentParser(add_help=False)
    wave_parser.add_argument(
        "direction",
        type=str,
        choices=["ltr", "rtl"],
        help="Direction of wave",
    )

    # Options for animated effects
    animated_parser = argparse.ArgumentParser(add_help=False)
    animated_parser.add_argument(
        "--speed", type=int, choices=range(1, 5), default=1, help="Animation speed"
    )

    # Effects
    effect_subparsers.add_parser(
        "static", help="Static color", parents=[global_parser, custom_parser]
    )

    effect_subparsers.add_parser(
        "breath",
        help="Fade light in and out",
        parents=[global_parser, custom_parser, animated_parser],
    )

    effect_subparsers.add_parser(
        "hue",
        help="Transition across hue circle",
        parents=[global_parser, animated_parser],
    )

    effect_subparsers.add_parser(
        "wave",
        help="Rainbow wawe",
        parents=[global_parser, animated_parser, wave_parser],
    )

    effect_subparsers.add_parser("off", help="Turn light off")

    args = argparser.parse_args()

    # Use controller
    controller = LedController()
    data = controller.build_control_string(
        effect=args.effect,
        colors=getattr(args, "colors", None),
        speed=getattr(args, "speed", 1),
        brightness=getattr(args, "brightness", 1),
        wave_direction=getattr(args, "direction", None),
    )
    controller.send_control_string(data)
