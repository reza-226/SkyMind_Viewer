# sim/models/delay.py
def uplink_delay_s(data_mb: float, bandwidth_mbps: float, propagation_ms: float = 5.0) -> float:
    # time(s) = (Mb / Mbps) + propagation(s)
    if bandwidth_mbps <= 0:
        return 1e9
    return (max(0.0, data_mb) / bandwidth_mbps) + (propagation_ms / 1000.0)

def downlink_delay_s(result_mb: float, bandwidth_mbps: float, propagation_ms: float = 5.0) -> float:
    if bandwidth_mbps <= 0:
        return 1e9
    return (max(0.0, result_mb) / bandwidth_mbps) + (propagation_ms / 1000.0)

def processing_delay_s(cycles: float, cpu_cps: float) -> float:
    if cpu_cps <= 0:
        return 1e9
    return max(0.0, cycles) / cpu_cps
