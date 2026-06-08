#pragma once
#include <stdint.h>
static inline uint64_t rdmsr(uint32_t m) { uint32_t l,h; __asm__ volatile("rdmsr":"=a"(l),"=d"(h):"c"(m)); return ((uint64_t)h<<32)|l; }
static inline void wrmsr(uint32_t m, uint64_t v) { uint32_t l=v&0xFFFFFFFF,h=v>>32; __asm__ volatile("wrmsr"::"a"(l),"d"(h),"c"(m)); }
