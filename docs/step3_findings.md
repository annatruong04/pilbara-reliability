# Step 3 findings: cyclone severity and Port Hedland throughput

## Data

- 137 months, January 2015 to July 2026
- 10 months with a Category 3 or above cyclone
- Throughput: Pilbara Ports monthly cargo statistics (real, published)
- Cyclones: Bureau of Meteorology tropical cyclone database (real, published)
- No synthetic data is used anywhere in this analysis

## Method

Ordinary least squares regression of monthly throughput on cyclone
severity, controlling for calendar month and a linear time trend.
Four specifications were run, varying how severity is measured, so
the result can be checked for robustness rather than resting on one
convenient choice.

## Results

| model                | term              |   coef_mt |   std_err |   ci_low |   ci_high |   p_value |   adj_r2 |   n |
|:---------------------|:------------------|----------:|----------:|---------:|----------:|----------:|---------:|----:|
| M1 severity count    | total_severity    |   -0.7835 |    0.2114 |  -1.2019 |   -0.365  |    0.0003 |   0.8    | 137 |
| M2 distance weighted | weighted_severity |   -1.662  |    0.3803 |  -2.4148 |   -0.9091 |    0      |   0.8076 | 137 |
| M3 severe indicator  | severe            |   -2.3511 |    0.7796 |  -3.8943 |   -0.808  |    0.0031 |   0.793  | 137 |
| M4 weighted plus lag | weighted_severity |   -1.6603 |    0.3816 |  -2.4157 |   -0.9048 |    0      |   0.8063 | 137 |

## Preferred specification

Each unit of proximity-weighted cyclone severity is associated with
a -1.66 Mt change in monthly throughput (95% CI -2.41 to -0.91, p = 0.000).

## Limitations

1. Only 10 severe events, so intervals are wide.
2. Monthly aggregation dilutes a multi-day disruption.
3. Throughput is a proxy for production; stockpiles absorb short stoppages.
4. Port Hedland serves several miners, not Rio Tinto alone.
5. Association, not established causation.
6. The 200 km proximity decay scale is an assumption, stated openly.
