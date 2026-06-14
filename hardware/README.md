# Kobe Studio Hardware Gate

Kobe Studio includes this endpoint for coin, cash, NFC, or POS hardware controllers:

```http
POST /api/hardware/trigger
Content-Type: application/json

{"key":"YOUR_GATE_KEY","amount":"1"}
```

Admin settings:

```text
Hardware gate required = true
Hardware gate key = YOUR_GATE_KEY
Gate amount = 1
```

Simple ESP32 logic:

```cpp
// Pseudocode
// 1. Connect to Wi-Fi
// 2. Wait for a pulse/button input
// 3. Send HTTP POST to /api/hardware/trigger
// 4. Body: {"key":"YOUR_GATE_KEY","amount":"1"}
```

Recommended wiring:

```text
Hardware pulse output -> ESP32 GPIO input
Hardware GND          -> ESP32 GND
Use optocoupler/relay isolation if the external hardware voltage is not 3.3V logic.
```

Keep the gate key private and change it from the default before using the system at an event.
