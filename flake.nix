{
  description = "ЭЛЕМЕНТАРНО — доказательный детектив по фотографиям";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      pkgsFor = system: nixpkgs.legacyPackages.${system};
    in
    {
      devShells = forAllSystems (system:
        let pkgs = pkgsFor system; in
        {
          default = pkgs.mkShell {
            name = "elementarno";
            packages = [
              (pkgs.python3.withPackages (ps: with ps; [ pillow numpy requests ]))
              pkgs.jq
              pkgs.ruff
              pkgs.curl
            ];
            shellHook = ''
              export PYTHONPATH="$PWD/tools:${PYTHONPATH:-}"
              echo "ЭЛЕМЕНТАРНО: python3 -m tools.elementarno.cli --help"
            '';
          };
        });

      apps = forAllSystems (system:
        let pkgs = pkgsFor system; in
        {
          elementarno = {
            type = "app";
            program = "${pkgs.writeShellApplication {
              name = "elementarno";
              runtimeInputs = [ (pkgs.python3.withPackages (ps: with ps; [ pillow ])) ];
              text = ''
                export PYTHONPATH="$PWD/tools:${PYTHONPATH:-}"
                exec python3 -m tools.elementarno.cli "$@"
              '';
            }}/bin/elementarno";
          };
        });

      checks = forAllSystems (system:
        let pkgs = pkgsFor system; in
        {
          tests = pkgs.runCommand "elementarno-tests" {
            nativeBuildInputs = [ pkgs.python3 ];
          } ''
            cp -r ${self} source
            chmod -R +w source
            cd source
            PYTHONPATH="$PWD/tools" python3 -m unittest discover -s tests -t . >&2
            touch $out
          '';
        });
    };
}
