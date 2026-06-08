#include "kernel/string.h"
void *memcpy(void *d, const void *s, uint64_t n) { uint8_t *dd=(uint8_t*)d; const uint8_t *ss=(const uint8_t*)s; while(n--)*dd++=*ss++; return d; }
void *memset(void *s, int c, uint64_t n) { uint8_t *ss=(uint8_t*)s; while(n--)*ss++=(uint8_t)c; return s; }
int memcmp(const void *a, const void *b, uint64_t n) { const uint8_t *aa=(const uint8_t*)a,*bb=(const uint8_t*)b; for(uint64_t i=0;i<n;i++)if(aa[i]!=bb[i])return aa[i]-bb[i]; return 0; }
uint64_t strlen(const char *s) { uint64_t i=0; while(s[i])i++; return i; }
