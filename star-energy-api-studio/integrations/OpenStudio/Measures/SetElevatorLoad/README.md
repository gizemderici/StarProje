# Set Elevator Load

Asansor motoru tanimin anma gucunu mutlak deger olarak yazar. Tohum modeldeki 5000 W dogrulanmamis bir TEPE degeridir, surekli bagli yuk degil; bkz. docs/baseline_assumptions.md. Bu degisken tam olarak o belirsizligi tarar.

## Argumanlar

- `elevator_power_w` (Double, varsayilan `5000.0`) — Elevator motor connected power (W)
- `definition_name_pattern` (String, varsayilan `asansor`) — Name pattern identifying the elevator definition

Karar degiskeni tanimi: `engine/parameters.py`.
