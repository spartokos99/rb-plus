#pragma once
#include <algorithm>
#include <array>
#include <cwchar>

namespace rbq {
// Index zero leaves Rekordbox's own setting in control; 1..24 are permutations.
inline std::array<int,4> layoutOrder(unsigned index) {
    std::array<int,4> result{0,1,2,3};
    if (index>24) return result;
    for (unsigned i=1;i<index;++i) std::next_permutation(result.begin(),result.end());
    return result;
}
inline unsigned parseLayoutOrder(const wchar_t* value) {
    if (!value || std::wcslen(value)!=4) return 0;
    for (unsigned i=1;i<=24;++i) {
        const auto order=layoutOrder(i);
        bool match=true;
        for (int j=0;j<4;++j) match=match && value[j]==L'1'+order[j];
        if (match) return i;
    }
    return 0;
}
}
