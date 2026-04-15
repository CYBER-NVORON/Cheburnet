import sys

from cheburnet.app import main


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--zapret-worker":
        from cheburnet.zapret_worker import main as worker_main

        sys.argv = [sys.argv[0], *sys.argv[2:]]
        raise SystemExit(worker_main())
    main()
