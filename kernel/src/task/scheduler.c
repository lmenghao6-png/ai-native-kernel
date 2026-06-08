#include "kernel/scheduler.h"
#include "kernel/serial.h"
static scheduler_stats_t stats;
void scheduler_init(uint32_t t) { stats.time_slice_ticks = t; serial_write("[sched] init\n"); }
void scheduler_submit(struct task *t) { (void)t; }
struct task *scheduler_pick_next(struct task *c, enum task_stop_reason r) { (void)c;(void)r; return 0; }
void scheduler_tick(void) {}
scheduler_stats_t scheduler_get_stats(void) { return stats; }
