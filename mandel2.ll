
; mandel_gradient.ll — Mandelbrot ASCII con gradiente y threshold como argumento

@xmin   = constant double -2.000000e+00
@xmax   = constant double  1.000000e+00
@ymin   = constant double -1.500000e+00
@ymax   = constant double  1.500000e+00
@width  = constant double  8.000000e+01  ; 80.0
@height = constant double  4.000000e+01  ; 40.0

; Gradiente: 10 niveles + terminador NUL
@.gradient = private unnamed_addr constant [11 x i8] c" .:-=+*#%@\00"

declare i32 @putchar(i32)

; ---- i32 in_mandelbrot_iters(double x0, double y0, i32 n) ----
; Devuelve steps en [0..n], donde steps==n => no escapó (punto "dentro")
define i32 @in_mandelbrot_iters(double %x0, double %y0, i32 %n) {
entry:
  %x     = alloca double
  %y     = alloca double
  %left  = alloca i32
  %steps = alloca i32
  store double 0.0, double* %x
  store double 0.0, double* %y
  store i32 %n, i32* %left
  store i32 0, i32* %steps
  br label %loop.cond

loop.cond:
  ; continuar si left > 0 y (x*x + y*y) <= 4.0
  %lcur = load i32, i32* %left
  %has  = icmp sgt i32 %lcur, 0

  %xv = load double, double* %x
  %yv = load double, double* %y
  %xx = fmul double %xv, %xv
  %yy = fmul double %yv, %yv
  %r2 = fadd double %xx, %yy
  %in = fcmp ole double %r2, 4.000000e+00

  %go = and i1 %has, %in
  br i1 %go, label %loop.body, label %loop.end

loop.body:
  ; xtemp = x*x - y*y + x0
  %x1 = load double, double* %x
  %y1 = load double, double* %y
  %x2 = fmul double %x1, %x1
  %y2 = fmul double %y1, %y1
  %re = fsub double %x2, %y2
  %xt = fadd double %re, %x0

  ; y = 2*x*y + y0
  %xy = fmul double %x1, %y1
  %t2 = fmul double 2.000000e+00, %xy
  %yn = fadd double %t2, %y0
  store double %yn, double* %y

  ; x = xtemp
  store double %xt, double* %x

  ; left-- ; steps++
  %l1 = load i32, i32* %left
  %l2 = add nsw i32 %l1, -1
  store i32 %l2, i32* %left

  %s1 = load i32, i32* %steps
  %s2 = add nsw i32 %s1, 1
  store i32 %s2, i32* %steps

  br label %loop.cond

loop.end:
  ; si salió por radio>2, steps ya es el usado; si por left==0, steps==n
  %sret = load i32, i32* %steps
  ret i32 %sret
}

; ---- i32 mandel(i32 threshold) ----
define i32 @mandel(i32 %thresh) {
entry:
  %dx = alloca double
  %dy = alloca double
  %x  = alloca double
  %y  = alloca double

  %xminv = load double, double* @xmin
  %xmaxv = load double, double* @xmax
  %yminv = load double, double* @ymin
  %ymaxv = load double, double* @ymax
  %wv    = load double, double* @width
  %hv    = load double, double* @height

  ; dx, dy
  %xspan = fsub double %xmaxv, %xminv
  %yspan = fsub double %ymaxv, %yminv
  %dxv   = fdiv double %xspan, %wv
  %dyv   = fdiv double %yspan, %hv
  store double %dxv, double* %dx
  store double %dyv, double* %dy

  ; y = ymax
  store double %ymaxv, double* %y
  br label %outer.cond

outer.cond:
  %yc = load double, double* %y
  %keepY = fcmp oge double %yc, %yminv      ; y >= ymin
  br i1 %keepY, label %outer.body, label %outer.end

outer.body:
  ; x = xmin
  store double %xminv, double* %x
  br label %inner.cond

inner.cond:
  %xc = load double, double* %x
  %keepX = fcmp olt double %xc, %xmaxv      ; x < xmax
  br i1 %keepX, label %inner.body, label %inner.end

inner.body:
  ; steps = in_mandelbrot_iters(x, y, thresh)
  %yc2 = load double, double* %y
  %steps = call i32 @in_mandelbrot_iters(double %xc, double %yc2, i32 %thresh)

  ; idx = (steps * 9) / thresh      ; 0..9
  %mul = mul nsw i32 %steps, 9
  %idx = sdiv i32 %mul, %thresh

  ; ch = gradient[idx]
  %idx64 = sext i32 %idx to i64
  %gptr = getelementptr inbounds [11 x i8], [11 x i8]* @.gradient, i32 0, i64 %idx64
  %ch8  = load i8, i8* %gptr
  %ch32 = zext i8 %ch8 to i32
  %pv   = call i32 @putchar(i32 %ch32)

  ; x += dx
  %dxc = load double, double* %dx
  %xnext = fadd double %xc, %dxc
  store double %xnext, double* %x
  br label %inner.cond

inner.end:
  ; newline y y -= dy
  %nl = call i32 @putchar(i32 10)
  %dyc = load double, double* %dy
  %yc3 = load double, double* %y
  %ynext = fsub double %yc3, %dyc
  store double %ynext, double* %y
  br label %outer.cond

outer.end:
  ret i32 0
}

; ---- int main() { return mandel(1000); } ----
define i32 @main() {
entry:
  %r = call i32 @mandel(i32 1000)
  ret i32 %r
}