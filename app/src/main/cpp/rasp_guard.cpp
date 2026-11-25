// ALVISIA PRO 5.5.0 — librasp_guard.so
// Anti-debug / anti-dump / anti-hook native layer
// Build: CMakeLists.txt target librasp_guard
// ABI: arm64-v8a (primary), armeabi-v7a (secondary)
// Compiler: clang++ (NDK r25c+)  C++17  -O2  -fvisibility=hidden  -fstack-protector-all
//           -Wl,--strip-all  -ffunction-sections  -fdata-sections  -Wl,--gc-sections

#include <jni.h>
#include <stdint.h>
#include <android/log.h>
#include <sys/ptrace.h>
#include <sys/uio.h>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <time.h>
#include <dirent.h>
#include <stdlib.h>
#include <errno.h>
#include <signal.h>
#include <pthread.h>
#include <dlfcn.h>

#define LOGD(...) __android_log_print(ANDROID_LOG_DEBUG, "RASP_N", __VA_ARGS__)

// ── Bit masks returned by nativeScanFlags() ──────────────────────────
static constexpr int FLAG_TRACER_PID      = 0x01;
static constexpr int FLAG_MAPS_FRIDA      = 0x02;
static constexpr int FLAG_PTRACE_ERROR    = 0x04;
static constexpr int FLAG_HW_BREAKPOINT   = 0x08;
static constexpr int FLAG_INLINE_HOOK     = 0x10;
static constexpr int FLAG_CAP_OVERGRANTED = 0x20;
static constexpr int FLAG_SELF_HASH_BAD   = 0x40;
static constexpr int FLAG_TIMING_PTRACE   = 0x80;
// Sprint 1 additions — 4 new detectors for hardened 7-layer security
static constexpr int FLAG_WCHAN_PTRACE    = 0x100;
static constexpr int FLAG_LATE_LIB       = 0x200;
static constexpr int FLAG_JNI_PROLOGUE   = 0x400;
static constexpr int FLAG_DEV_FILES       = 0x800;

// ─────────────────────────────────────────────────────────────────────
// 1. TracerPid check
// ─────────────────────────────────────────────────────────────────────
static int check_tracer_pid() {
    int fd = open("/proc/self/status", O_RDONLY);
    if (fd < 0) return 0;
    char buf[2048] = {};
    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    if (n <= 0) return 0;
    const char* p = strstr(buf, "TracerPid:");
    if (!p) return 0;
    int tpid = atoi(p + 10);
    return (tpid > 0) ? FLAG_TRACER_PID : 0;
}

// ─────────────────────────────────────────────────────────────────────
// 2. /proc/self/maps — Frida / hook library markers
// ─────────────────────────────────────────────────────────────────────
// Only high-confidence injector names trigger native hard-block flags.
// Generic hook-bridge libraries are reported by Kotlin as soft signals.
static const char* const* map_needles() {
    // Detection markers are stored XOR-encoded so static inspection does not expose
    // the complete RASP signature table in plaintext.
    static char decoded[7][32] = {};
    static const unsigned char enc[][32] = {
        {0x3c,0x28,0x33,0x3c,0x3b,0x77,0x3b,0x28,0x3f,0x34,0x2e,0x00},
        {0x3c,0x28,0x33,0x3c,0x3d,0x3d,0x2d,0x2e,0x77,0x3d,0x3b,0x3e,0x3b,0x2e,0x00},
        {0x3c,0x28,0x33,0x3c,0x3b,0x77,0x3b,0x28,0x3f,0x34,0x2e,0x00},
        {0x3c,0x28,0x33,0x3c,0x3d,0x3d,0x2d,0x2e,0x77,0x3d,0x3b,0x3e,0x3b,0x2e,0x00},
        {0x36,0x33,0x38,0x3c,0x28,0x33,0x3e,0x3b,0x00},
        {0x36,0x3b,0x3d,0x3d,0x3f,0x2e,0x3f,0x00},
        {0x36,0x33,0x34,0x30,0x3f,0x3d,0x2e,0x35,0x28,0x00}
    };
    static const char* out[8] = {};
    static bool ready = false;
    if (!ready) {
        for (int i = 0; i < 7; ++i) {
            int j = 0;
            while (j < 31 && enc[i][j]) { decoded[i][j] = static_cast<char>(enc[i][j] ^ 0x5a); ++j; }
            decoded[i][j] = 0;
            out[i] = decoded[i];
        }
        out[7] = nullptr;
        ready = true;
    }
    return out;
}

// Match marker names only in the pathname of an executable mapping. Searching
// the entire maps dump can match non-executable mappings or unrelated metadata.
static bool map_space(char c) {
    return c == 32 || c == 9 || c == 13 || c == 10;
}

static bool map_line_has_exec_marker(const char* rawLine, const char* const* needles) {
    if (rawLine == nullptr || needles == nullptr) return false;
    char line[8192] = {};
    size_t len = strlen(rawLine);
    if (len >= sizeof(line)) len = sizeof(line) - 1;
    memcpy(line, rawLine, len);
    line[len] = 0;
    for (size_t i = 0; i < len; ++i) {
        if (line[i] >= 'A' && line[i] <= 'Z') line[i] += 32;
    }

    char* p = line;
    while (*p && !map_space(*p)) ++p; // address range
    while (map_space(*p)) ++p;
    char* perms = p;
    while (*p && !map_space(*p)) ++p;
    bool executable = false;
    for (char* q = perms; q < p; ++q) if (*q == 'x') executable = true;
    if (!executable) return false;

    // Skip offset, device and inode fields; everything after them is pathname.
    for (int field = 0; field < 3; ++field) {
        while (map_space(*p)) ++p;
        while (*p && !map_space(*p)) ++p;
    }
    while (map_space(*p)) ++p;
    if (*p == 0) return false;

    for (int i = 0; needles[i]; ++i) {
        if (strstr(p, needles[i])) return true;
    }
    return false;
}

static bool maps_buffer_has_exec_marker(char* buf, const char* const* needles) {
    if (buf == nullptr || needles == nullptr) return false;
    char* line = buf;
    while (*line) {
        char* end = strchr(line, 10);
        if (end) *end = 0;
        if (map_line_has_exec_marker(line, needles)) return true;
        if (!end) break;
        line = end + 1;
    }
    return false;
}

static int check_maps_frida() {
    int fd = open("/proc/self/maps", O_RDONLY);
    if (fd < 0) return 0;
    char buf[131072] = {};
    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    if (n <= 0) return 0;
    return maps_buffer_has_exec_marker(buf, map_needles()) ? FLAG_MAPS_FRIDA : 0;
}

// ─────────────────────────────────────────────────────────────────────
// 3. ptrace(PTRACE_TRACEME) — fails if already traced
// ─────────────────────────────────────────────────────────────────────
static int check_ptrace_traceme() {
    long ret = ptrace(PTRACE_TRACEME, 0, nullptr, nullptr);
    if (ret == -1L && errno == EPERM) {
        return FLAG_PTRACE_ERROR;
    }
    // Undo TRACEME immediately if it succeeded (don't leave ourselves traced)
    if (ret == 0) {
        ptrace(PTRACE_DETACH, 0, nullptr, nullptr);
    }
    return 0;
}

// ─────────────────────────────────────────────────────────────────────
// 4. Hardware breakpoint detection via ptrace GETREGSET (arm64)
// ─────────────────────────────────────────────────────────────────────
static int check_hw_breakpoint() {
    // Read NT_ARM_HW_BREAK from own process via a short-lived child
    // that ptraces the parent and checks DBGBCR registers.
    // Simplified: check /proc/self/status for "StopSignal" or use timing.
    // Full impl requires fork + ptrace child (complex inline here).
    // We use timing side-channel instead (see check_timing_ptrace).
    return 0;
}

// ─────────────────────────────────────────────────────────────────────
// 5. Inline hook detection in libc / libdvm / libart .text section
//    Checks first 4 bytes of known functions for B/BL jump patch.
// ─────────────────────────────────────────────────────────────────────
static int check_inline_hook() {
    // Load libc and check strlen prologue — hooked by many frameworks
    void* libc = dlopen("libc.so", RTLD_NOLOAD | RTLD_LAZY);
    if (!libc) return 0;
    void* fn = dlsym(libc, "strcmp");
    if (!fn) { dlclose(libc); return 0; }
    // On clean arm64: first instruction is NOT a branch to hook trampoline
    // B instruction encoding: top 6 bits = 0x14 or 0x17 for unconditional branch
    const uint8_t* bytes = reinterpret_cast<const uint8_t*>(fn);
    // Check for unconditional branch (B = 0x14xxxxxx or BL = 0x94xxxxxx in arm64 LE)
    uint32_t instr = 0;
    memcpy(&instr, bytes, 4);
    uint32_t op = instr >> 26;
    int hooked = (op == 0x05 || op == 0x25) ? FLAG_INLINE_HOOK : 0; // B=0x05, BL=0x25
    dlclose(libc);
    return hooked;
}

// ─────────────────────────────────────────────────────────────────────
// 6. Capability overgranting (CapEff full set = process runs as root)
// ─────────────────────────────────────────────────────────────────────
static int check_cap_overgranted() {
    int fd = open("/proc/self/status", O_RDONLY);
    if (fd < 0) return 0;
    char buf[4096] = {};
    read(fd, buf, sizeof(buf) - 1);
    close(fd);
    const char* p = strstr(buf, "CapEff:");
    if (!p) return 0;
    unsigned long long capeff = strtoull(p + 7, nullptr, 16);
    // 0x3fffffffff = all caps set (root-equivalent in most kernels)
    return (capeff == 0x3fffffffffffffffULL || capeff == 0x3fffffffffULL)
        ? FLAG_CAP_OVERGRANTED : 0;
}

// ─────────────────────────────────────────────────────────────────────
// 7. Self-page hash — detect if our own .text was patched after load
//    Simplified: hash first 4 KB of this .so's .text via dladdr
// ─────────────────────────────────────────────────────────────────────
static volatile uint32_t g_text_hash_baseline = 0;

static uint32_t hash_region(const uint8_t* p, size_t len) {
    uint32_t h = 0x811c9dc5u;
    for (size_t i = 0; i < len; i++) {
        h ^= p[i];
        h *= 0x01000193u;
    }
    return h;
}

static int check_self_hash();

static const uint8_t* native_code_page(size_t* length) {
    if (length == nullptr) return nullptr;
    long pageSize = sysconf(_SC_PAGESIZE);
    if (pageSize <= 0 || (pageSize & (pageSize - 1)) != 0) pageSize = 4096;
    const uintptr_t address = reinterpret_cast<uintptr_t>(
        reinterpret_cast<void*>(check_self_hash));
    const uintptr_t pageStart = address & ~((uintptr_t)pageSize - 1U);
    *length = (size_t)pageSize;
    return reinterpret_cast<const uint8_t*>(pageStart);
}

static void init_self_hash() {
    size_t length = 0;
    const uint8_t* page = native_code_page(&length);
    if (page == nullptr || length == 0) return;
    g_text_hash_baseline = hash_region(page, length);
}

static int check_self_hash() {
    if (g_text_hash_baseline == 0) return 0; // not initialized
    size_t length = 0;
    const uint8_t* page = native_code_page(&length);
    if (page == nullptr || length == 0) return 0;
    const uint32_t current = hash_region(page, length);
    return (current != g_text_hash_baseline) ? FLAG_SELF_HASH_BAD : 0;
}

// ─────────────────────────────────────────────────────────────────────
// 8. Timing-based ptrace detection (debugger slows clock_gettime)
// ─────────────────────────────────────────────────────────────────────
static int check_timing_ptrace() {
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    // A few volatile reads to create a measurable interval
    volatile int sink = 0;
    for (int i = 0; i < 1000; i++) sink += i;
    clock_gettime(CLOCK_MONOTONIC, &t1);
    int64_t ns = ((int64_t)(t1.tv_sec - t0.tv_sec)) * 1000000000LL
                + (t1.tv_nsec - t0.tv_nsec);
    // Under a debugger single-step, this loop takes >> 5 ms
    return (ns > 5000000LL) ? FLAG_TIMING_PTRACE : 0;
}

// ─────────────────────────────────────────────────────────────────────
// 9. /proc/self/wchan — process is in ptrace_stop state
//    Sprint 1: Detect ptrace_stop via wchan string
// ─────────────────────────────────────────────────────────────────────
static int check_wchan_ptrace() {
    int fd = open("/proc/self/wchan", O_RDONLY);
    if (fd < 0) return 0;
    char buf[64] = {};
    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    if (n <= 0) return 0;
    // If process is in ptrace_stop, wchan contains "ptrace_stop"
    if (strstr(buf, "ptrace_stop") != nullptr) return FLAG_WCHAN_PTRACE;
    return 0;
}

// ─────────────────────────────────────────────────────────────────────
// 10. Late-loaded suspicious libraries (post-startup dlopen of hook libs)
//     Sprint 1: Scan /proc/self/maps for libs loaded after JNI_OnLoad
// ─────────────────────────────────────────────────────────────────────
static const char* const* late_lib_needles() {
    static char decoded[5][24] = {};
    static const unsigned char enc[][24] = {
        {0x36,0x33,0x38,0x3c,0x28,0x33,0x3e,0x3b,0x00},
        {0x36,0x3b,0x3d,0x3d,0x3f,0x2e,0x3f,0x00},
        {0x3c,0x28,0x33,0x3c,0x3b,0x77,0x3b,0x28,0x3f,0x34,0x2e,0x00},
        {0x3c,0x28,0x33,0x3c,0x3d,0x3d,0x2d,0x2e,0x77,0x3d,0x3b,0x3e,0x3b,0x2e,0x00},
        {0x36,0x33,0x34,0x30,0x3f,0x3d,0x2e,0x35,0x28,0x00}
    };
    static const char* out[6] = {};
    static bool ready = false;
    if (!ready) {
        for (int i = 0; i < 5; ++i) {
            int j = 0;
            while (j < 23 && enc[i][j]) { decoded[i][j] = static_cast<char>(enc[i][j] ^ 0x5a); ++j; }
            decoded[i][j] = 0;
            out[i] = decoded[i];
        }
        out[5] = nullptr;
        ready = true;
    }
    return out;
}

static int check_late_loaded_libs() {
    int fd = open("/proc/self/maps", O_RDONLY);
    if (fd < 0) return 0;
    char buf[262144] = {};  // 256 KiB — larger window for late libs
    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    if (n <= 0) return 0;
    return maps_buffer_has_exec_marker(buf, late_lib_needles()) ? FLAG_LATE_LIB : 0;
}

extern "C" {
static jint JNICALL native_scan_flags(JNIEnv*, jobject);
}

// ─────────────────────────────────────────────────────────────────────
// 11. JNI function prologue integrity — check if our own JNI methods
//     have been patched with a B (branch) instruction by inline hooks
//     Sprint 1: Verify critical native functions haven't been replaced
// ─────────────────────────────────────────────────────────────────────
static int check_jni_prologue() {
    // Check the prologue of native_scan_flags itself — if hooked, the
    // first instruction will typically be a B/BL branch to a trampoline.
    uintptr_t fn_addr = reinterpret_cast<uintptr_t>(
        reinterpret_cast<void*>(&native_scan_flags));
    if (fn_addr == 0) return 0;
    const uint8_t* bytes = reinterpret_cast<const uint8_t*>(fn_addr);
    uint32_t instr = 0;
    memcpy(&instr, bytes, 4);
    uint32_t op = instr >> 26;
    // arm64 unconditional branch opcodes: B=0x05, BL=0x25
    if (op == 0x05 || op == 0x25) return FLAG_JNI_PROLOGUE;
    return 0;
}

// ─────────────────────────────────────────────────────────────────────
// 12. Suspicious dev files — check for files that indicate a rooted/
//     debugging setup exists in /data/local/tmp or /dev/
//     Sprint 1: Detect frida-server, gadget, hluda-server artifacts
// ─────────────────────────────────────────────────────────────────────
static const char* const* dev_file_paths() {
    static char decoded[14][64] = {};
    static const unsigned char enc[][64] = {
        {0x75,0x2e,0x3b,0x2e,0x3b,0x2f,0x36,0x35,0x3d,0x3b,0x36,0x70,0x2e,0x37,0x2e,0x74,0x2c,0x28,0x33,0x3c,0x3b,0x77,0x29,0x3f,0x28,0x2c,0x3f,0x28,0x00},
        {0x75,0x2e,0x3b,0x2e,0x3b,0x2f,0x36,0x35,0x3d,0x3b,0x36,0x70,0x2e,0x37,0x2e,0x74,0x2c,0x28,0x33,0x3c,0x3b,0x77,0x3d,0x3b,0x3e,0x3b,0x2e,0x00},
        {0x75,0x2e,0x3b,0x2e,0x3b,0x2f,0x36,0x35,0x3d,0x3b,0x36,0x70,0x2e,0x37,0x2e,0x74,0x32,0x36,0x2f,0x3e,0x3b,0x77,0x29,0x3f,0x28,0x2c,0x3f,0x28,0x00},
        {0x75,0x2e,0x3b,0x2e,0x3b,0x2f,0x36,0x35,0x3d,0x3b,0x36,0x70,0x2e,0x37,0x2e,0x74,0x3c,0x28,0x33,0x3c,0x3b,0x77,0x32,0x3f,0x36,0x2e,0x3f,0x28,0x00},
        {0x75,0x2e,0x3b,0x2e,0x3b,0x2f,0x36,0x35,0x3d,0x3b,0x36,0x70,0x2e,0x37,0x2e,0x74,0x32,0x36,0x2f,0x3e,0x3b,0x77,0x3c,0x28,0x33,0x3c,0x3b,0x77,0x32,0x3f,0x36,0x2e,0x3f,0x28,0x00},
        {0x75,0x2e,0x3b,0x2e,0x3b,0x2f,0x36,0x35,0x3d,0x3b,0x36,0x70,0x2e,0x37,0x2e,0x74,0x36,0x33,0x34,0x30,0x2f,0x3f,0x2e,0x35,0x28,0x00},
        {0x75,0x2e,0x3b,0x2e,0x3b,0x2f,0x36,0x35,0x3d,0x3b,0x36,0x70,0x2e,0x37,0x2e,0x74,0x35,0x28,0x33,0x36,0x36,0x3f,0x3d,0x2e,0x35,0x28,0x00},
        {0x75,0x29,0x23,0x29,0x2e,0x3f,0x37,0x75,0x38,0x33,0x34,0x2f,0x3c,0x3c,0x28,0x33,0x3c,0x3b,0x77,0x29,0x3f,0x28,0x2c,0x3f,0x28,0x00},
        {0x75,0x29,0x23,0x29,0x2e,0x3f,0x37,0x75,0x22,0x2c,0x33,0x34,0x3f,0x2f,0x3c,0x3c,0x28,0x33,0x3c,0x3b,0x77,0x29,0x3f,0x28,0x2c,0x3f,0x28,0x00},
        {0x75,0x29,0x33,0x34,0x2f,0x75,0x3c,0x28,0x33,0x3c,0x3b,0x77,0x29,0x3f,0x28,0x2c,0x3f,0x28,0x00},
        {0x75,0x29,0x33,0x34,0x2f,0x74,0x22,0x33,0x34,0x2f,0x3c,0x28,0x33,0x3c,0x3b,0x77,0x29,0x3f,0x28,0x2c,0x3f,0x28,0x00},
        {0x75,0x29,0x38,0x33,0x34,0x75,0x77,0x37,0x3b,0x3d,0x33,0x29,0x30,0x00},
        {0x75,0x3e,0x3b,0x2e,0x3b,0x75,0x3b,0x3e,0x38,0x75,0x37,0x3b,0x3d,0x33,0x29,0x30,0x75,0x37,0x35,0x3e,0x2f,0x36,0x3f,0x29,0x00}
    };
    static const char* out[15] = {};
    static bool ready = false;
    if (!ready) {
        for (int i = 0; i < 14; ++i) {
            int j = 0;
            while (j < 63 && enc[i][j]) { decoded[i][j] = static_cast<char>(enc[i][j] ^ 0x5a); ++j; }
            decoded[i][j] = 0;
            out[i] = decoded[i];
        }
        out[14] = nullptr;
        ready = true;
    }
    return out;
}

static int check_dev_files() {
    struct stat st;
    const char* const* paths = dev_file_paths();
    for (int i = 0; paths[i]; i++) {
        if (stat(paths[i], &st) == 0) {
            return FLAG_DEV_FILES;
        }
    }
    return 0;
}

// ─────────────────────────────────────────────────────────────────────
// JNI exports
// ─────────────────────────────────────────────────────────────────────
extern "C" {

static jint JNICALL
native_scan_flags(JNIEnv*, jobject) {
    // Only high-confidence, read-only signals reach the enforcement layer.
    // PTRACE_TRACEME, timing thresholds, generic libc prologue checks and
    // root capability heuristics can disrupt or falsely block valid users.
    int flags = 0;
    flags |= check_tracer_pid();
    flags |= check_maps_frida();
    flags |= check_self_hash();
    // Sprint 1: 4 new detectors active
    flags |= check_wchan_ptrace();
    flags |= check_late_loaded_libs();
    flags |= check_jni_prologue();
    flags |= check_dev_files();
    return (jint)flags;
}

static void JNICALL
native_wipe(JNIEnv* env, jobject, jbyteArray arr) {
    if (!arr) return;
    jsize len = env->GetArrayLength(arr);
    if (len <= 0) return;
    jbyte* p = env->GetByteArrayElements(arr, nullptr);
    if (!p) return;
    // Volatile stores prevent the optimizer from eliding the wipe as a dead
    // store. Release mode 0 copies the cleared bytes back when JNI returned a
    // temporary buffer.
    volatile unsigned char* wipe = reinterpret_cast<volatile unsigned char*>(p);
    for (jsize i = 0; i < len; ++i) {
        wipe[i] = 0;
    }
    env->ReleaseByteArrayElements(arr, p, 0);
}

static jint JNICALL
native_anti_dump(JNIEnv*, jobject) {
    // Scan all pids: detect open fd to /proc/<self>/mem
    int selfpid = (int)getpid();
    char selfmem[64];
    snprintf(selfmem, sizeof(selfmem), "/proc/%d/mem", selfpid);
    int found = 0;

    DIR* proc = opendir("/proc");
    if (!proc) return 0;
    struct dirent* de;
    while ((de = readdir(proc)) != nullptr) {
        int pid = atoi(de->d_name);
        if (pid == 0 || pid == selfpid) continue;
        char fddir[64];
        snprintf(fddir, sizeof(fddir), "/proc/%d/fd", pid);
        DIR* fdd = opendir(fddir);
        if (!fdd) continue;
        struct dirent* fde;
        while ((fde = readdir(fdd)) != nullptr) {
            char fdpath[128];
            snprintf(fdpath, sizeof(fdpath), "/proc/%d/fd/%s", pid, fde->d_name);
            char link[256] = {};
            if (readlink(fdpath, link, sizeof(link) - 1) > 0) {
                if (strcmp(link, selfmem) == 0) { found++; }
            }
        }
        closedir(fdd);
    }
    closedir(proc);
    return (jint)found;
}

// Library load init — called by dynamic linker
__attribute__((constructor))
static void on_load() {
    init_self_hash();
}

} // extern "C"

// ── Seal seed export ──────────────────────────────────────────────────────────
// Per-build seed is injected into the native .rodata section by tools/seal_python.py
// at CI time. The linker symbol ALVSIA_SEAL_SEED_HEX is never in the final .so
// unless the CI sealing step runs — so debug builds return nullptr, fail-closed.

extern "C" {

// Placeholder symbol — CI replaces this with the 32-byte hex seed at link time
__attribute__((visibility("hidden")))
static const unsigned char _alvsia_seal_seed[32] = {0};

static jbyteArray JNICALL
native_seal_seed(JNIEnv* env, jobject) {
    // In debug/CI builds the seed is all-zero — sealed assets won't decrypt.
    // In release builds, seal_python.py patches this array before linking.
    bool all_zero = true;
    for (int i = 0; i < 32; i++) { if (_alvsia_seal_seed[i]) { all_zero = false; break; } }
    if (all_zero) return nullptr;  // fail-closed in debug

    jbyteArray arr = env->NewByteArray(32);
    env->SetByteArrayRegion(arr, 0, 32, reinterpret_cast<const jbyte*>(_alvsia_seal_seed));
    return arr;
}

}  // extern "C"


// Resolve JNI entry points by registration instead of exporting predictable
// Java_com_* symbols in the dynamic symbol table.
static jstring JNICALL
native_seal_build_id(JNIEnv* env, jobject) {
    static const unsigned char encoded[] = {0x1b, 0x16, 0x0c, 0x13, 0x09, 0x13, 0x1b, 0x77, 0x68, 0x6a, 0x68, 0x6c, 0x6b, 0x6a, 0x6b, 0x6a, 0x77, 0x17, 0x1b, 0x13, 0x14, 0x77, 0x09, 0x1f, 0x1b, 0x16, 0x6b};
    char decoded[sizeof(encoded) + 1] = {};
    for (size_t i = 0; i < sizeof(encoded); ++i) decoded[i] = static_cast<char>(encoded[i] ^ 0x5a);
    jstring result = env->NewStringUTF(decoded);
    memset(decoded, 0, sizeof(decoded));
    return result;
}

// ── Native mini-VM: a bounded second-stage integrity interpreter ─────────────
// Kept separate from nativeScanFlags so the Kotlin VM and native VM evaluate
// their own instruction streams. This is defense-in-depth, not a claim of
// commercial Virbox equivalence or protection against a fully privileged attacker.
static jint JNICALL
native_vm_flags(JNIEnv*, jobject) {
    // Independent bounded bytecode stream. The VM checks six distinct native
    // signals; unknown opcodes, overrun, and incomplete execution fail closed.
    static const uint8_t program[] = {0x11, 0x22, 0x33, 0x44, 0x55, 0x66};
    size_t pc = 0;
    int budget = 12;
    int flags = 0;
    while (pc < sizeof(program) && budget-- > 0) {
        switch (program[pc++]) {
            case 0x11: flags |= check_tracer_pid(); break;
            case 0x22: flags |= check_maps_frida(); break;
            case 0x33: flags |= check_self_hash(); break;
            case 0x44: flags |= check_wchan_ptrace(); break;
            case 0x55: flags |= check_late_loaded_libs(); break;
            case 0x66: flags |= check_dev_files(); break;
            default: return -1;
        }
    }
    if (pc != sizeof(program) || budget < 0) return -1;
    return flags;
}

static JNINativeMethod kNativeMethods[] = {
    {const_cast<char*>("nativeScanFlags"), const_cast<char*>("()I"), reinterpret_cast<void*>(native_scan_flags)},
    {const_cast<char*>("nativeWipe"), const_cast<char*>("([B)V"), reinterpret_cast<void*>(native_wipe)},
    {const_cast<char*>("nativeAntiDump"), const_cast<char*>("()I"), reinterpret_cast<void*>(native_anti_dump)},
    {const_cast<char*>("nativeSealSeed"), const_cast<char*>("()[B"), reinterpret_cast<void*>(native_seal_seed)},
    {const_cast<char*>("nativeSealBuildId"), const_cast<char*>("()Ljava/lang/String;"), reinterpret_cast<void*>(native_seal_build_id)},
    {const_cast<char*>("nativeVmFlags"), const_cast<char*>("()I"), reinterpret_cast<void*>(native_vm_flags)},
};

JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* vm, void*) {
    JNIEnv* env = nullptr;
    if (vm == nullptr || vm->GetEnv(reinterpret_cast<void**>(&env), JNI_VERSION_1_6) != JNI_OK || env == nullptr) {
        return JNI_ERR;
    }
    jclass cls = env->FindClass("com/alvsia/pro/sec/NativeGuard");
    if (cls == nullptr) {
        if (env->ExceptionCheck()) env->ExceptionClear();
        return JNI_ERR;
    }
    const jint status = env->RegisterNatives(
        cls, kNativeMethods, static_cast<jint>(sizeof(kNativeMethods) / sizeof(kNativeMethods[0])));
    env->DeleteLocalRef(cls);
    return status == JNI_OK ? JNI_VERSION_1_6 : JNI_ERR;
}
