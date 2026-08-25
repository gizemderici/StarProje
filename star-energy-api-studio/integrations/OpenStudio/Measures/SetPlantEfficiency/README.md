# Set Plant Efficiency

Chiller:Electric:EIR referans COP ve Boiler:HotWater anma verimini gunceller. Performans egrilerine dokunmaz.

## Argumanlar

- `chiller_cop` (Double, varsayilan `5.5`) — Chiller reference COP (W/W)
- `boiler_efficiency` (Double, varsayilan `0.9`) — Boiler nominal thermal efficiency

Faz 2 kapsaminda yazildi. Karar degiskeni tanimi:
`engine/parameters.py`.
