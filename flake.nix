{
  description = "Coq Shell";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    nixpkgs,
    flake-utils,
    ...
  }:
    flake-utils.lib.eachDefaultSystem (
      system: let
        pkgs = import nixpkgs {inherit system;};
      in
        with pkgs; {
          devShells.default = mkShell {
            packages = with coqPackages; [
              llvmPackages_20.openmp
              pkgs.coq
              clang
              stdlib
              python3
              rocqPackages.vsrocq-language-server
            ];

            shellHook = ''
              unset COQPATH
            '';
          };
        }
    );
}
