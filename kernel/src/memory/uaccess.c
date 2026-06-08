#include "kernel/uaccess.h"
#include "kernel/serial.h"
void uaccess_init(void) { serial_write("[uaccess] init\n"); }
bool copy_from_user(void *to, const void *from, uint64_t size) {
    for(uint64_t i=0;i<size;i++) ((uint8_t*)to)[i]=((volatile uint8_t*)from)[i];
    return true;
}
bool copy_to_user(void *to, const void *from, uint64_t size) { return copy_from_user(to, from, size); }
