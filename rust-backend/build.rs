fn main() {
    println!("cargo:rerun-if-changed=src/legacy_regex.c");
    cc::Build::new()
        .file("src/legacy_regex.c")
        .compile("legacy_regex");
}
