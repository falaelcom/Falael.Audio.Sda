import math

def compound_sigmoid(x, x0, xmin_range, ymin_range, xmax_range, ymax_range):
    assert xmin_range < x0, "xmin_range must be less than x0"
    assert x0 < xmax_range, "x0 must be less than xmax_range"
    assert ymin_range < 0, "ymin_range must be negative"
    assert ymax_range > 0, "ymax_range must be positive"
    assert -1 < ymin_range, "ymin_range must be greater than -1"
    assert ymax_range < 1, "ymax_range must be less than 1"

    delta_x_low = x0 - xmin_range
    delta_y_low = -ymin_range  # Positive value assumed via assertion
    delta_x_up = xmax_range - x0
    delta_y_up = ymax_range  # Positive value assumed via assertion
    
    # Compute k_low for left half
    if delta_y_low >= 1 or delta_y_low <= 0:
        raise ValueError("delta_y_low must be in (0, 1)")
    k_low = (1 / delta_x_low) * math.log((1 + delta_y_low) / (1 - delta_y_low))
    
    # Compute k_up for right half
    if delta_y_up >= 1 or delta_y_up <= 0:
        raise ValueError("delta_y_up must be in (0, 1)")
    k_up = (1 / delta_x_up) * math.log((1 + delta_y_up) / (1 - delta_y_up))
    
    if x <= x0:
        exp_term = math.exp(-k_low * (x - x0))
        return (2 / (1 + exp_term)) - 1
    else:
        exp_term = math.exp(-k_up * (x - x0))
        return (2 / (1 + exp_term)) - 1