import argparse
import operator
import re
from . import provider as provider
from . import satellite as satellite

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check the configuration's consistency and download SP3 files",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")
    doctor_parser = subparsers.add_parser(
        "coverage",
        help="Print the number of providers for each satellite",
    )
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()

    if args.command == "coverage":
        sp3_id_to_providers_count = {
            sp3_id: 0 for sp3_id in satellite.sp3_to_satellite.keys()
        }
        extra: list[tuple[provider.Provider, re.Pattern]] = []
        for candidate_provider in provider.providers:
            for sp3_pattern in candidate_provider.sp3_patterns:
                matched_at_least_once = False
                for sp3_id in satellite.sp3_to_satellite.keys():
                    if sp3_pattern.match(sp3_id) is not None:
                        matched_at_least_once = True
                        sp3_id_to_providers_count[sp3_id] += 1
                if not matched_at_least_once:
                    extra.append((candidate_provider, sp3_pattern))
        providers_count_to_satellites: dict[int, list[satellite.Satellite]] = {}
        for sp3_id, providers_count in sp3_id_to_providers_count.items():
            if not providers_count in providers_count_to_satellites:
                providers_count_to_satellites[providers_count] = []
            providers_count_to_satellites[providers_count].append(
                satellite.sp3_to_satellite[sp3_id]
            )
        for satellites in providers_count_to_satellites.values():
            satellites.sort(key=operator.attrgetter("sp3"))
        if len(extra) > 0:
            print("patterns that did not match any satellites:")
            for candidate_provider, sp3_pattern in extra:
                print(
                    f"    {sp3_pattern.pattern} (provider {candidate_provider.name_template})"
                )
        for providers_count, satellites in sorted(
            providers_count_to_satellites.items()
        ):
            if providers_count == 0:
                print("no providers")
            elif providers_count == 1:
                print("1 provider")
            else:
                print(f"{providers_count} providers")
            for satellite in satellites:
                print(f"    {satellite.sp3.decode()} ({satellite.name})")
            print()
