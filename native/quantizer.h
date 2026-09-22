#pragma once
#include <algorithm>
#include <cmath>

namespace rbq {
struct State { bool valid = false; double bpm = 0, step = 0, selected = 0; };
struct Result { float delta; double target; bool quantized; };

// Hysteresis is 10% of a step beyond each half-step boundary.
// Limits describe the native pitch-delta range, not the rate range.
inline Result quantize(float delta, double bpm, double step, float minimum,
                       float maximum, State& state) noexcept {
    Result unchanged{delta, 0, false};
    if (!std::isfinite(delta) || !std::isfinite(bpm) || bpm <= 0 || bpm >= 1000 ||
        !std::isfinite(minimum) || !std::isfinite(maximum) || minimum > maximum ||
        (step != 0.1 && step != 1.0)) {
        state.valid = false;
        return unchanged;
    }
    const double raw = bpm * (1.0 + static_cast<double>(delta));
    const double low = std::max(1.0, std::ceil(bpm * (1.0 + minimum) / step));
    const double high = std::floor(bpm * (1.0 + maximum) / step);
    if (!std::isfinite(raw) || low > high || high > 1000000) {
        state.valid = false;
        return unchanged;
    }
    double bin = std::floor(raw / step + 0.5);
    if (state.valid && state.bpm == bpm && state.step == step &&
        raw >= state.selected - 0.6 * step && raw <= state.selected + 0.6 * step) {
        bin = std::round(state.selected / step);
    }
    bin = std::clamp(bin, low, high);
    const double target = bin * step;
    const float output = static_cast<float>(target / bpm - 1.0);
    if (!std::isfinite(output) || output < minimum || output > maximum) {
        state.valid = false;
        return unchanged;
    }
    state = {true, bpm, step, target};
    return {output, target, true};
}
}
