#include "layout_order.h"
#include <cassert>
#include <set>
#include <iostream>

int main() {
    std::set<std::array<int,4>> all;
    for (unsigned index=1;index<=24;++index) {
        const auto order=rbq::layoutOrder(index);
        assert(all.insert(order).second);
        assert((std::set<int>(order.begin(),order.end())==std::set<int>{0,1,2,3}));
        wchar_t stored[5]{};
        for (int slot=0;slot<4;++slot) stored[slot]=static_cast<wchar_t>(L'1'+order[slot]);
        assert(rbq::parseLayoutOrder(stored)==index);
    }
    assert((rbq::layoutOrder(0)==std::array<int,4>{0,1,2,3}));
    assert((rbq::layoutOrder(24)==std::array<int,4>{3,2,1,0}));
    assert((rbq::layoutOrder(13)==std::array<int,4>{2,0,1,3}));
    for (const wchar_t* bad : {L"",L"default",L"1111",L"123",L"12345",L"0234",L"1235",L"12 4",L"4321junk"})
        assert(rbq::parseLayoutOrder(bad)==0);
    assert(rbq::parseLayoutOrder(nullptr)==0);
    std::cout << "All 24 layout permutations and invalid settings passed\n";
}
