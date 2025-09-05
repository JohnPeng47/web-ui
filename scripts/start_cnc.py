import asyncio
import sys
sys.path.append("cnc")

from cnc.main import main 

if __name__ == "__main__":
    asyncio.run(main())