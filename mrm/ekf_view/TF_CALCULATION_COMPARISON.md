# TF Calculation Comparison: Autoware vs Awkernel

## Summary

This document compares TF-related behavior between Autoware and Awkernel output handling.

## TF Tree

Both systems use the same structure:

```text
map
  `- base_link
      `- imu_link
```

## Key Observations

1. Parent/child frame IDs are consistent (`map` -> `base_link`).
2. Pose and orientation values are passed consistently through Odometry.
3. Covariance values are consistent with EKF output definitions.
4. Timestamp representation differs by source format and conversion step.

## Static TF Consideration

Two components can publish static TF depending on launch configuration. Prefer one authoritative publisher to keep debugging straightforward.

## Recommendation

Use one static TF publishing path consistently across your launch flow.

## Conclusion

No fundamental difference was found in TF computation logic between Autoware and Awkernel pathways in this setup. Most issues are operational (publisher overlap, startup ordering, or missing TF publication), not mathematical inconsistency.
