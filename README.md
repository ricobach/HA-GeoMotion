# HA-GeoMotion

GeoMotion is a Home Assistant custom integration for GPS-based movement detection from existing `person` and `device_tracker` entities.

It determines whether a tracked entity is moving or stationary by analysing recent GPS history rather than comparing only the latest two updates or relying on Home Assistant zone states.

## Features

- Tracks `person` and `device_tracker` entities that expose latitude/longitude
- One GeoMotion device per tracked entity
- `Moving` binary sensor using Home Assistant's `moving` device class
- Rolling in-memory GPS history
- Uses an older reference position rather than the immediately previous update
- GPS-accuracy-aware movement threshold to suppress normal GPS drift
- Configurable history window, comparison age, minimum reference age, movement threshold, fallback GPS accuracy and stationary hold time
- One-time Home Assistant Recorder history recovery after restart
- No continuous Recorder queries during normal operation
- Diagnostic attributes including displacement, GPS accuracy, reference age, sample count and `evaluation_reason`
- Copies the source entity picture to the GeoMotion binary sensor

## Default settings

- History window: 600 seconds (10 minutes)
- Preferred comparison age: 300 seconds (5 minutes)
- Minimum reference age: 60 seconds
- Minimum movement distance: 20 metres
- Fallback GPS accuracy: 25 metres
- Moving-to-stationary hold time: 120 seconds

The effective movement threshold is the larger of the configured minimum distance and the combined uncertainty of the current and reference GPS samples.

## State behaviour

`on` means meaningful GPS movement has been detected. `off` means the tracked entity appears stationary. `unknown` is reserved for cases where there is not enough reliable GPS information, the history has become stale, or a geographic distance cannot be calculated.

Once GeoMotion has established a reliable moving/stationary state, a brief lack of a suitable historical reference retains that state instead of bouncing back to `unknown`.

The `evaluation_reason` attribute explains the current decision. Values include:

- `moving`
- `stationary`
- `stationary_hold`
- `holding_previous_state`
- `insufficient_history`
- `stale_history`
- `distance_unavailable`

## Restart recovery

When GeoMotion starts it performs one Recorder history query for the configured recent history window and rebuilds its in-memory GPS history. After initialization, live Home Assistant state updates are the normal runtime data source and Recorder is not queried continuously.

## Installation with HACS

1. Add `https://github.com/ricobach/HA-GeoMotion` to HACS as a custom **Integration** repository.
2. Install **GeoMotion**.
3. Restart Home Assistant if requested.
4. Go to **Settings > Devices & services > Add integration** and search for **GeoMotion**.
5. Choose the first `person` or `device_tracker` and configure its movement settings.
6. Use **Add service** on the GeoMotion integration to add more tracked entities.

## Devices and entities

Each configured source gets its own GeoMotion device. For example:

```text
Rico
└── Moving
```

The binary sensor exposes useful diagnostics without exposing the internal rolling sample history, including current/reference coordinates, GPS accuracy, reference age, displacement, effective threshold, sample count, last meaningful movement and source entity.

## Privacy and data handling

GeoMotion does not send location data to an external API. It only processes location attributes already present in your Home Assistant instance. Recent GPS samples are kept in memory and are not exposed as helpers or high-frequency state attributes.

## Notes

GeoMotion uses GPS coordinates only. It does not infer movement from `home`, `not_home`, or zone names.

This is an independent Home Assistant custom integration.
