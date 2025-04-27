📡 A9G GPS Tracker Project

This project started as part of my goal to eventually build a full car tracking system.
Before working on the full system, I wanted to first understand how the A9G board works — how it handles GPS data, GSM communication, and how to control it at a low level.

To make development easier, I'm using the [gprs_a9 MicroPython](https://github.com/pulkin/micropython/tree/master/ports/gprs_a9) port, which provides a Python environment for the A9G board.
This lets me quickly prototype, send commands, and handle GPS/GSM features directly in Python.

Through this project, I'm learning and practicing:

    🔌 UART communication — setting up serial communication with the board

    📡 GPS basics — getting live location data from satellites

    🛜 GSM fundamentals — sending messages and handling mobile network communication

    💬 AT Commands — managing the module’s features via text commands(Planned*)

    ⚡ Microcontroller programming — integrating the A9G with external systems

    🐍 MicroPython development — programming the A9G in a higher-level, faster way

This is a first step toward building a complete car tracking system — and a great way to get hands-on with embedded systems, GPS, and IoT communication!


### 📶 SIM Provider

For this project, I'm using a SIM card from [Hologram.io](https://www.hologram.io/).

Hologram provides IoT-focused SIM cards that work globally across multiple networks, making it a great choice for projects like GPS trackers and remote sensors. Their plans are flexible, with pay-as-you-go options, which is ideal for development and testing without committing to large contracts.

Key reasons I chose Hologram.io:
- 🌍 Global coverage — works with a wide range of carriers worldwide
- 💵 Flexible pricing — no large monthly fees, pay only for what you use
- 🔧 Developer-friendly — easy setup, good documentation, and APIs for managing SIMs

You can manage your SIMs, monitor data usage, and configure alerts through their online dashboard, which is super helpful during prototyping and testing phases.



Here’s my current configuration. In the future, I plan to mount everything onto a chassis and power it with a battery.
<img src="A9GSetup.jpg" alt="The current setup" width="500"/>

