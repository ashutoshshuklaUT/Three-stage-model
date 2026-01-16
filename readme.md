# Coordinated Grid Resilience Planning

Three-stage stochastic optimization for co-optimizing permanent substation hardening and temporary flood barrier deployment against hurricane-induced flooding.

## Overview

This code implements a three-stage stochastic mixed-integer programming model that coordinates long-term hardening investments with short-term Tiger Dam deployments to protect transmission grids from hurricane flooding. The model determines optimal budget allocation between permanent and temporary protective measures while minimizing expected load loss.

## Key Features

- **Three-stage stochastic optimization** - Co-optimizes mitigation (permanent hardening), preparedness (Tiger Dam deployment), and response (load shedding) decisions
- **Physics-based flood modeling** - Integrates NOAA storm-surge scenarios with flood impact-sensitive DC power flow
- **Correlated flooding** - Captures spatial dependencies in flood impacts across substations
- **Budget allocation** - Determines optimal split between long-term and short-term resilience measures
- **Comprehensive sensitivity analysis** - Effects of VOLL, restoration time, Tiger Dam effectiveness, and hardening costs

## Installation
```bash
