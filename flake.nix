{
  # Nix Flake for this package
  description = "rhasselbaum/snapcast-tools package Flake";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        pname = "snapcast-tools";
      in
      {
        packages = {
          snapcast-tools = pkgs.stdenv.mkDerivation {
            inherit pname;
            version = "git";

            src = ./.;
            buildInputs = [
              (pkgs.python3.withPackages (p: with p; [ ]))
              pkgs.makeWrapper
              pkgs.pipewire
            ];

            installPhase = ''
              mkdir -p $out/bin
              cp $src/src/pw_snapcast_sink.py $out/bin
              chmod +x $out/bin/pw_snapcast_sink.py
              makeWrapper $out/bin/pw_snapcast_sink.py $out/bin/pw-snapcast-sink \
                --set PATH ${pkgs.pipewire}/bin
            '';
          };
        };

        defaultPackage = self.packages.${system}.snapcast-tools;
      }
    );
  }