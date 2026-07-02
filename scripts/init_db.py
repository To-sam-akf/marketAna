from back_end.app.core.database import create_database_tables


def main() -> None:
    create_database_tables()
    print("database tables created")


if __name__ == "__main__":
    main()
