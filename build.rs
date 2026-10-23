fn main() {
    #[cfg(feature = "desktop")]
    slint_build::compile("ui/app.slint").expect("compilar layout Slint");
}
