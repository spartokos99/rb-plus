#include "quantizer.h"
#include <cassert>
#include <cstring>
#include <iostream>

static float pitch(double target, double base = 174) {
    return static_cast<float>(target / base - 1);
}
int main() {
    rbq::State s;
    auto q = rbq::quantize(pitch(127.73, 128), 128, 1, -0.06f, 0.06f, s);
    assert(q.quantized && q.target == 128);
    s = {};
    q = rbq::quantize(pitch(175.37), 174, 1, -0.06f, 0.06f, s);
    assert(q.quantized && q.target == 175);
    assert(std::abs(174 * (1.0 + q.delta) - 175) < 0.00001);
    // Boundary noise must not toggle the chosen bin.
    for (double raw : {175.49, 175.51, 175.59, 175.48})
        assert(rbq::quantize(pitch(raw), 174, 1, -0.06f, 0.06f, s).target == 175);
    assert(rbq::quantize(pitch(175.61), 174, 1, -0.06f, 0.06f, s).target == 176);
    assert(rbq::quantize(pitch(175.41), 174, 1, -0.06f, 0.06f, s).target == 176);
    assert(rbq::quantize(pitch(175.39), 174, 1, -0.06f, 0.06f, s).target == 175);
    // Step and track changes reset hysteresis.
    assert(std::abs(rbq::quantize(pitch(175.37), 174, 0.1, -0.06f, 0.06f, s).target - 175.4) < 1e-9);
    assert(rbq::quantize(pitch(127.73, 128), 128, 1, -0.06f, 0.06f, s).target == 128);
    // Full sweep in both directions, including edges and sudden fader jumps.
    for (double step : {0.1, 1.0}) {
        s = {};
        for (int i = -6000; i <= 6000; ++i) {
            auto r = rbq::quantize(i / 100000.0f, 174, step, -0.06f, 0.06f, s);
            assert(r.quantized && r.delta >= -0.06f && r.delta <= 0.06f);
            assert(std::abs(r.target / step - std::round(r.target / step)) < 1e-8);
            assert(std::abs(174 * (1.0 + r.delta) - r.target) < 0.00001);
        }
        for (int i = 6000; i >= -6000; --i)
            assert(rbq::quantize(i / 100000.0f, 174, step, -0.06f, 0.06f, s).quantized);
    }
    const float negativeZero = -0.0f;
    q = rbq::quantize(negativeZero, 174, 0, -0.06f, 0.06f, s);
    assert(!q.quantized && !std::memcmp(&q.delta, &negativeZero, sizeof(float)));
    assert(!rbq::quantize(0, NAN, 1, -0.06f, 0.06f, s).quantized);
    assert(!rbq::quantize(NAN, 174, 1, -0.06f, 0.06f, s).quantized);
    assert(!rbq::quantize(0, 0, 1, -0.06f, 0.06f, s).quantized);
    assert(!rbq::quantize(0, 174.2, 1, 0, 0, s).quantized);
    std::cout << "quantizer: all checks passed\n";
}
