{
  description = "SlimeVR Morpho Charger";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { nixpkgs, ... }:
    let
      forAllSystems = nixpkgs.lib.genAttrs [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};

          # Python library for the Excamera I2CDriver
          i2cdriver =
            ps:
            ps.buildPythonPackage rec {
              pname = "i2cdriver";
              version = "1.0.6";
              pyproject = true;
              src = ps.fetchPypi {
                inherit pname version;
                hash = "sha256-6ISrnSC045H6rv1g4PktmzyzUluSxbEHobcMhM+I6E8=";
              };
              postPatch = ''
                sed -i '/^\[project.scripts\]/,/^$/d' pyproject.toml
              '';
              build-system = [ ps.setuptools ];
              dependencies = [ ps.pyserial ];
              pythonImportsCheck = [ "i2cdriver" ];
            };

        in
        {
          default = pkgs.mkShell {
            packages = [
              # eeprom/generate.py, plus the i2cdriver library for flashing with an I2CDriver
              (pkgs.python3.withPackages (ps: [ (i2cdriver ps) ]))
              # pushes and runs eeprom/flash_pico.py on the Pico
              pkgs.mpremote
            ];
          };
        }
      );
    };
}
