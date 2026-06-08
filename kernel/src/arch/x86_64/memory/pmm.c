#include "kernel/pmm.h"
#include "kernel/serial.h"
#include "kernel/string.h"
#include <stddef.h>
static uint8_t bitmap[131072];
static uint64_t total = 0, free_pages = 0;
void pmm_init(void *resp) {
    (void)resp;
    for(int i=0;i<(int)sizeof(bitmap);i++) bitmap[i]=0xFF;
    total = sizeof(bitmap)*8; free_pages = total;
    serial_write("[pmm] ready\n");
}
uint64_t pmm_alloc(void) {
    for(uint64_t i=0;i<sizeof(bitmap);i++) {
        if(bitmap[i]==0xFF) continue;
        for(int b=0;b<8;b++) { if(!(bitmap[i]&(1<<b))){bitmap[i]|=(1<<b);free_pages--;return(i*8+b)*0x1000;} }
    }
    return 0;
}
pmm_stats_t pmm_get_stats(void) { pmm_stats_t s={total,free_pages}; return s; }

