__attribute__((naked)) void _start(void) {
    __asm__ volatile(
        "leaq msg(%rip), %rdi\n"
        "movq len(%rip), %rsi\n"
        "movl $0x12, %eax\n"
        "int $0x80\n"
        "movl $0x13, %eax\n"
        "xorl %edi, %edi\n"
        "int $0x80\n"
        "msg: .ascii \"Hello from Bastion!\\n\"\n"
        "len: .quad 20\n"
    );
}
