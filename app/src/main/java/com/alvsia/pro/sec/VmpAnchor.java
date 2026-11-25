package com.alvsia.pro.sec;

/**
 * Small deterministic native/VMP anchor.
 *
 * The release protector explicitly virtualizes this class. The method is also
 * executed at each protected-operation boundary so the VMP path is exercised
 * by real application logic rather than being dead code.
 */
public final class VmpAnchor {
    private VmpAnchor() {}

    public static boolean healthy() {
        int a = 0x13579BDF;
        int b = 0x2468ACE0;
        int x = ((a ^ 0x5A17C3D9) + (b ^ 0x6E31A927));
        x = Integer.rotateLeft(x, 7) ^ 0x4F1BBCDC;
        x += Integer.rotateLeft(a, 3);
        return x != 0 && x != a && x != b;
    }
}
