# Set Lighting Power

Iki OS:Lights:Definition nesnesinin W/m2 degerini gunceller. Ayirt etme ad desenine gore yapilir, mevcut degere gore degil.

## Argumanlar

- `primary_w_m2` (Double, varsayilan `7.0`) — Primary lighting power density (W/m2)
- `secondary_w_m2` (Double, varsayilan `3.0`) — Secondary lighting power density (W/m2)
- `primary_name_pattern` (String, varsayilan `ofis`) — Name pattern identifying the primary definition

Faz 2 kapsaminda yazildi. Karar degiskeni tanimi:
`engine/parameters.py`.
