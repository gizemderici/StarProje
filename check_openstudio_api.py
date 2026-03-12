def main() -> None:
    try:
        import openstudio as openstudio
    except ImportError as exc:
        print("OpenStudio Python API yuklu degil veya Python tarafindan bulunamiyor.")
        print(f"Hata: {exc}")
        return

    print("OpenStudio Python API kullanilabilir.")
    print("OpenStudio surumu:", openstudio.openStudioVersion())


if __name__ == "__main__":
    main()
