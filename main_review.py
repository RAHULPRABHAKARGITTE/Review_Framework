from g1.main_g1 import run_g1
from g3.main_g3 import run_g3
from g4.main_g4 import run_g4
from g5.main_g5 import run_g5
from g7.main_g7 import run_g7


def main():
    print("Starting Review Framework...")

    run_g1()
    print("G1 review completed.\n")

    run_g3()
    print("G3 review completed.\n")

    run_g4()
    print("G4 review completed.\n")

    run_g5()
    print("G5 review completed.\n")

    run_g7()
    print("G7 review completed.\n")


if __name__ == "__main__":
    main()
