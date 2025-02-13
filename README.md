# Solana Meme Coin Trading Bot: Operation Manual and Technical Deep Dive

## Overview

This Solana Meme Coin Trading Bot is an automated system designed to capitalize on the volatile and often unpredictable nature of meme coins within the Solana ecosystem.  It proactively scans for newly emerging and trending meme coins, analyzes market conditions using technical indicators, and automatically executes buy or sell orders based on a predefined trading strategy.

**Key Design Principles:**

*   **Autonomous Operation:** The bot is designed for continuous, unattended operation, monitoring markets and executing trades without manual intervention once configured.
*   **Real-time Data Driven:** It leverages real-time data from Solana blockchain WebSockets and DexScreener API to make timely trading decisions.
*   **Strategy-Based Trading:** Trading actions are driven by a technical analysis strategy incorporating multiple indicators, aiming to identify potentially profitable opportunities.
*   **Data Persistence and Analysis:** All market data and trade executions are meticulously logged and stored in a TimescaleDB database for historical analysis, performance monitoring, and strategy refinement.
*   **Scalability and Maintainability:** The code is structured in a modular fashion using classes for each component, promoting scalability, easier maintenance, and future feature additions.
*   **Testnet Focus:**  The bot is primarily configured and intended for operation on the Solana Devnet, allowing for risk-free testing and strategy validation before considering live deployments (use with extreme caution and at your own risk on mainnet if you adapt it).

## Features: In Extreme Detail

1.  **New Meme Coin Discovery and Scanning:**
    *   **DexScreener Trending API Integration:** Continuously polls the DexScreener API's `/token-boosts/top/v1` endpoint. This endpoint provides a list of trending tokens based on DexScreener's proprietary algorithms, which often highlights newly listed and actively traded meme coins.
    *   **Liquidity and Volume Filtering:** Fetched tokens are not blindly traded. The bot intelligently filters these tokens based on two critical metrics:
        *   **Liquidity Threshold:**  A configurable `MEME_COIN_LIQUIDITY_THRESHOLD` is used. Only tokens with liquidity *below* this threshold are considered as potential targets. The rationale here is to identify extremely *new* meme coins where liquidity is still developing and potentially presents higher volatility and rapid price movements.
        *   **Minimum Volume:**  Only tokens exhibiting positive trading volume (`volumeUsd > 0`) are considered. This ensures the token is not completely stagnant and there's actual market activity.
    *   **Duplicate Token Prevention:**  A `last_seen_tokens` set is maintained to prevent repetitive scanning and trading of the same token. Once a token mint address is processed, it's added to this set for the current session.
    *   **Automated Buy Orders on Candidate Tokens:** When a token passes the liquidity and volume filters, and is new, the bot automatically executes a market buy order via the `TradeExecutor`. The order quantity is determined by the `ORDER_QUANTITY` environment variable.

2.  **Technical Analysis Driven Trading Strategy:**
    *   **Multi-Indicator Approach:** The `StrategyManager` employs a combination of four common technical indicators to generate trading signals:
        *   **Simple Moving Average (SMA) (30 periods):**  Calculates the average price over the last 30 periods (implicitly assuming price updates happen at regular intervals within the `strategy_loop`). SMA helps to smooth out price fluctuations and identify the overall trend direction.
        *   **Relative Strength Index (RSI) (14 periods):** Measures the magnitude of recent price changes to evaluate overbought or oversold conditions in the market. RSI values below 30 are generally considered oversold, and above 70 overbought.
        *   **Bollinger Bands (20 periods, 2 standard deviations):**  Consist of a middle band (SMA), an upper band (SMA + 2 standard deviations), and a lower band (SMA - 2 standard deviations). Bollinger Bands are used to measure market volatility and identify potential price breakouts or reversals. Prices nearing the lower band might suggest an oversold condition, and prices nearing the upper band, an overbought condition.
        *   **Moving Average Convergence Divergence (MACD) (12, 26, 9 periods):**  A trend-following momentum indicator that shows the relationship between two moving averages of a security's price. The MACD histogram (MACD line - Signal line) is used here. Positive histogram values suggest upward momentum, and negative values suggest downward momentum.
    *   **Scoring System for Signal Generation:** A simple scoring mechanism aggregates signals from the individual indicators:
        *   **Price Relative to Bollinger Bands:** If the current price is below the lower Bollinger Band, +1 point is added. If above the upper band, -1 point.
        *   **RSI Levels:** If RSI is below 30 (oversold), +1 point. If RSI is above 70 (overbought), -1 point.
        *   **MACD Histogram:** If the MACD histogram is positive, +1 point. If negative, -1 point.
        *   **Price Relative to SMA:** If the current price is above the SMA, +1 point. If below the SMA, -1 point.
    *   **Buy/Sell Signal Thresholds:**  Based on the total score:
        *   **Score ≥ 2: "BUY" Signal:**  Indicates a confluence of bullish signals across multiple indicators.
        *   **Score ≤ -2: "SELL" Signal:**  Indicates a confluence of bearish signals.
        *   **Score between -1 and 1: No Signal:** Neutral market condition, no action is taken.

3.  **Efficient Solana Token Swaps via Jupiter Aggregator API (v1):**
    *   **Jupiter API v1 Integration:**  Utilizes the Jupiter Aggregator API (specifically, the `/swap/v1/quote` and `/swap/v1/swap` endpoints) for fetching optimal swap routes and executing trades on Solana. The API endpoints are the updated v1 versions as of recent Jupiter API updates.
    *   **Quote Retrieval:** For each trade execution, the `TradeExecutor` first queries the `/swap/v1/quote` endpoint to get the best available swap route for the desired input and output tokens and amounts. Parameters include `inputMint`, `outputMint`, `amount`, and `slippageBps`.
    *   **Swap Transaction Construction and Signing:** Upon receiving a quote, the `TradeExecutor` constructs a swap transaction payload and sends it to the `/swap/v1/swap` endpoint. This API returns a serialized, unsigned Solana transaction.
    *   **Local Transaction Signing with Keypair:** The bot securely signs the unsigned transaction using the Solana keypair loaded from the `SECRET_KEY_B58` environment variable. This keypair is managed by the `SolanaKeypair` class, which handles Base58 decoding and `solders` library interactions.
    *   **Transaction Broadcasting:** The signed transaction is then broadcast to the Solana network using the `AsyncClient` connected to the specified `SOLANA_RPC_URL`.
    *   **Slippage Control:**  Slippage is set to a default of 1% (`slippage=1`) for market orders. This can be adjusted, but higher slippage tolerance increases the risk of unfavorable fills. Dynamic slippage control is also implemented via `dynamicSlippage: {"maxBps": 300}` in the swap request.
    *   **API Key Support (Optional):**  The bot supports using a Jupiter API key via the `JUPITER_API_KEY` environment variable. If provided, the API key is included in the `X-API-Key` header for API requests.

4.  **Robust Data Storage in TimescaleDB (PostgreSQL):**
    *   **TimescaleDB Integration:** Leverages TimescaleDB, a time-series database extension for PostgreSQL, for efficient storage and querying of market data and trade logs.
    *   **Database Schema:** Two tables are defined using `peewee_async`:
        *   **`market_data`:** Stores raw market data received from the WebSocket stream. Includes a `timestamp` field (DateTimeField) for time-series indexing and a `data` field (JSONField) to store structured or unstructured market data (e.g., log messages).
        *   **`trade_logs`:**  Records details of every trade execution, including timestamps and `trade_details` (JSONField) storing information such as signal type, price at execution, order parameters, Jupiter API responses, and any errors.
    *   **Asynchronous Database Operations:** All database interactions (connecting, storing data, closing connections) are handled asynchronously using `peewee_async` to avoid blocking the main event loop and ensure responsiveness.
    *   **Connection Pooling:** `PooledPostgresqlDatabase` from `peewee_async` is used to manage a pool of database connections, optimizing performance and resource usage.

5.  **Real-time Solana Blockchain Data Streaming:**
    *   **Solana WebSocket API:** Utilizes the Solana WebSocket API via the `solana.rpc.websocket_api` library to subscribe to real-time blockchain events.
    *   **Log Subscription:**  Subscribes to `logsSubscribe` method to receive transaction logs.  Currently, it's set up to subscribe to logs that mention the "mint" keyword and are associated with the Token Program (`TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`). This is intended to capture token minting events and possibly transfer activities (though the current filter is very broad).
    *   **Market Data Persistence from Stream:** Received log messages are extracted and stored in the `market_data` table of the TimescaleDB database for potential analysis, although the current usage in the provided code is limited (just storing raw logs).

6.  **Meme Coin Specific Scanner (WebSocket Based):**
    *   **Dedicated Meme Coin Log Monitoring:**  A separate `MemeCoinScanner` specifically focuses on monitoring Solana WebSocket logs for signals related to new meme coin activity.
    *   **Token Minted Log Parsing:** It attempts to parse log messages looking for the phrase "TokenMinted" which is a *hypothetical* log format indicating a new token mint event.  **Important Note:** The code makes assumptions about the format of these "TokenMinted" logs (e.g., expecting parts separated by '|' and key-value pairs within parts). In a real-world scenario, you would need to precisely understand the actual log message structure generated by relevant Solana programs or protocols indicating new meme coin creation.
    *   **Coin Detail Extraction:**  The `parse_log_for_coin_details` method tries to extract details like token mint address, initial supply, and potentially a "symbol" from the parsed log message, again based on assumed log formatting.
    *   **Meme Coin Filtering (Simple):**  The `filter_coin` method implements a rudimentary filtering logic:
        *   It checks if the token "symbol" (extracted from logs) contains "MEME" (case-insensitive).
        *   It calculates a very basic "liquidity proxy" (initial supply * trade amount) and compares it to `MEME_COIN_LIQUIDITY_THRESHOLD`. This proxy is extremely simplistic and not a reliable measure of actual liquidity.
        *   **Caution:** This filtering is very basic and likely needs significant refinement in a real-world application. Real meme coin filtering would require much more sophisticated techniques to assess project legitimacy, community engagement, smart contract analysis, and genuine liquidity.
    *   **Automated Buy Orders on "Detected" Meme Coins:** If a coin passes the very basic `filter_coin` checks, a market buy order is placed using the `TradeExecutor`.

## System Architecture: Component Breakdown

1.  **`DexScreenerScanner` Class:**
    *   **Responsibility:**  Periodically queries the DexScreener Trending API, filters trending tokens based on liquidity and volume thresholds, and triggers buy orders for qualifying tokens.
    *   **Dependencies:**
        *   `TradeExecutor`: For executing market orders.
        *   `DatabaseManager`: For storing trade logs.
        *   `aiohttp`: For making asynchronous HTTP requests to the DexScreener API.
        *   Environment variables: `TRENDING_API_ENDPOINT`, `MEME_COIN_LIQUIDITY_THRESHOLD`, `DEXSCREENER_POLL_INTERVAL`, `ORDER_QUANTITY`.
    *   **Workflow:**
        a.  Runs in a loop (`scan_for_new_coins` method).
        b.  Fetches trending tokens from `TRENDING_API_ENDPOINT` using `aiohttp`.
        c.  Iterates through fetched tokens, applying liquidity and volume filters (`MEME_COIN_LIQUIDITY_THRESHOLD`, `volumeUsd`, `liquidityUsd`).
        d.  Checks if the token mint has been seen before (`last_seen_tokens`).
        e.  If a token passes filters and is new, calls `trade_executor.execute_market_order()` to place a buy order.
        f.  Logs trade details using `db_manager.store_trade_log()`.
        g.  Waits for `DEXSCREENER_POLL_INTERVAL` before the next scan iteration.

2.  **`TradeExecutor` Class:**
    *   **Responsibility:**  Handles the execution of token swaps on Solana using the Jupiter Aggregator API. Manages Solana RPC client, keypair, and interaction with Jupiter API endpoints.
    *   **Dependencies:**
        *   `SolanaKeypair`: For managing the Solana private key and signing transactions.
        *   `AsyncClient` (from `solana.rpc.async_api`): For interacting with the Solana RPC endpoint.
        *   `aiohttp`: For making asynchronous HTTP requests to the Jupiter API.
        *   Environment variables: `SOLANA_RPC_URL`, `SECRET_KEY_B58`, `JUPITER_API_KEY`, `SOL_MINT`.
    *   **Workflow (`execute_swap` method):**
        a.  Takes input token mint, output token mint, and amount as arguments.
        b.  Constructs parameters for the Jupiter `/swap/v1/quote` API endpoint.
        c.  Sends a GET request to `/swap/v1/quote` using `aiohttp`.
        d.  Parses the JSON response to get the best swap route.
        e.  Constructs a payload for the `/swap/v1/swap` API endpoint, including the route and user public key.
        f.  Sends a POST request to `/swap/v1/swap` using `aiohttp`.
        g.  Receives a base64 encoded, unsigned Solana transaction in the response.
        h.  Decodes the base64 transaction using `base64.b64decode()`.
        i.  Deserializes the transaction using `SolanaTransaction.from_bytes()`.
        j.  Signs the transaction using `self.keypair.sign()`.
        k.  Serializes the signed transaction using `txn.serialize()`.
        l.  Sends the raw signed transaction to the Solana RPC endpoint using `self.client.send_raw_transaction()`.
        m. Returns the RPC response.
    *   **Workflow (`execute_market_order` method):**
        a.  A helper function to simplify market buy/sell orders.
        b.  Takes meme coin mint, side ("buy" or "sell"), and amount as arguments.
        c.  Determines `input_mint` and `output_mint` based on the `side`.
        d.  Calls `self.execute_swap()` with the appropriate mints and amount.

3.  **`StrategyManager` Class:**
    *   **Responsibility:** Implements the technical analysis trading strategy. Calculates indicators, generates trading signals (BUY, SELL, or None).
    *   **Dependencies:**
        *   `numpy`: For numerical operations (arrays for TA-Lib).
        *   `talib`: For technical indicator calculations (SMA, RSI, BBANDS, MACD).
    *   **Workflow (`generate_trading_signal` method):**
        a.  Maintains a list of recent prices (`self.prices`).
        b.  Converts `self.prices` to a `numpy` array.
        c.  Calculates SMA, RSI, Bollinger Bands, and MACD histogram using `talib` functions.
        d.  Gets the latest values of each indicator and the current price.
        e.  Applies the scoring system based on indicator conditions.
        f.  Returns "BUY", "SELL", or `None` based on the total score.
    *   **Workflow (`update_price` method):**
        a.  Appends a new price to the `self.prices` list.
        b.  Keeps the `self.prices` list to a maximum length of 1000 by removing the oldest price if necessary.

4.  **`MarketDataStreamer` Class:**
    *   **Responsibility:** Establishes a WebSocket connection to the Solana network, subscribes to log messages, and stores received market data (currently just logs) in the database.
    *   **Dependencies:**
        *   `DatabaseManager`: For storing market data.
        *   `solana_ws_connect` (from `solana.rpc.websocket_api`): For WebSocket connection.
        *   Environment variable: `WS_URL`.
    *   **Workflow (`stream_data` method):**
        a.  Connects to the Solana WebSocket at `WS_URL` using `solana_ws_connect`.
        b.  Sends a `logsSubscribe` request to subscribe to logs mentioning "mint" and related to the Token Program.
        c.  Enters a loop to continuously receive WebSocket messages.
        d.  For each message, processes the data. (Currently very basic log processing is implemented).
        e.  Stores received log messages in the `market_data` table using `db_manager.store_market_data()`.

5.  **`DatabaseManager` Class:**
    *   **Responsibility:**  Manages the connection to the TimescaleDB database, creates necessary tables (`market_data`, `trade_logs`), stores market data and trade logs, and closes the database connection.
    *   **Dependencies:**
        *   `PooledPostgresqlDatabase` (from `playhouse.postgres_ext`): For connection pooling to PostgreSQL.
        *   `AioModel`, `AutoField`, `DateTimeField`, `JSONField` (from `peewee_async` and `peewee`): For defining database models and interacting asynchronously.
        *   Environment variable: `TIMESCALE_DB_CONN_STR`.
    *   **Workflow (`connect` method):**
        a.  Parses the database connection URL from `TIMESCALE_DB_CONN_STR` using `parse_database_url()`.
        b.  Initializes `PooledPostgresqlDatabase` with parsed parameters.
        c.  Creates the `market_data` and `trade_logs` tables if they don't exist using `database.create_tables()`.
    *   **Workflow (`store_market_data` and `store_trade_log` methods):**
        a.  Create new model instances (`MarketData.aio_create` or `TradeLog.aio_create`) with provided data and the current timestamp.
        b.  Asynchronously save the data to the database.
    *   **Workflow (`close` method):**
        a.  Closes the database connection pool using `database.aio_close()`.

6.  **`MemeCoinScanner` Class:**
    *   **Responsibility:** Monitors Solana WebSocket logs specifically looking for signals of new meme coin creation (based on hypothetical "TokenMinted" logs), filters potential coins using very basic criteria, and triggers buy orders for coins that pass these rudimentary filters.
    *   **Dependencies:**
        *   `TradeExecutor`: For executing market orders.
        *   `DatabaseManager`: For storing trade logs.
        *   `solana_ws_connect` (from `solana.rpc.websocket_api`): For WebSocket connection.
        *   Environment variables: `WS_URL`, `MEME_COIN_LIQUIDITY_THRESHOLD`.
    *   **Workflow (`scan_and_trade` method):**
        a.  Connects to Solana WebSocket at `WS_URL`.
        b.  Subscribes to `logsSubscribe` with filters to try and capture relevant token minting/transfer logs.
        c.  Enters a loop to receive WebSocket messages.
        d.  For each message, checks if it's a log notification.
        e.  If it is a log notification and contains "TokenMinted" in the message (again, assuming this log format), calls `parse_log_for_coin_details()` to try and extract coin information.
        f.  Calls `filter_coin()` to apply basic filtering.
        g.  If the coin passes filters, calls `trade_executor.execute_market_order()` to buy.
        h.  Logs trade details via `db_manager.store_trade_log()`.

7.  **`SolanaKeypair` Class:**
    *   **Responsibility:** Loads and manages the Solana private key from the `SECRET_KEY_B58` environment variable. Provides methods for signing messages.
    *   **Dependencies:**
        *   `base58`: For Base58 decoding of the secret key.
        *   `SolanaKeypairPySolders`, `Pubkey` (from `solders.keypair` and `solders.pubkey`): For keypair handling.
        *   Environment variable: `SECRET_KEY_B58`.
    *   **Workflow (`__init__` method):**
        a.  Retrieves `SECRET_KEY_B58` from environment variables.
        b.  Decodes the Base58 string using `base58.b58decode()`.
        c.  Creates a `SolanaKeypairPySolders` object from the decoded bytes.
        d.  Extracts the public key as a `Pubkey` and the secret key as bytes.
    *   **Workflow (`sign` method):**
        a.  Takes a message (bytes) as input.
        b.  Signs the message using `self._keypair.sign_message()`.
        c.  Returns the signature as bytes.

## Why Python? The Rationale Behind Language Choice

While languages like C++ or Rust might offer performance advantages in certain aspects, Python was deliberately chosen for this project due to a combination of factors that prioritize rapid development, ease of use, and the availability of powerful libraries crucial for the bot's functionality:

*   **Rich Ecosystem of Data Science and Trading Libraries:** Python boasts an exceptionally rich ecosystem of libraries specifically designed for data analysis, numerical computation, and financial applications.
    *   **`talib` (TA-Lib):**  A cornerstone for technical analysis, providing a comprehensive suite of technical indicators with optimized performance. This library is essential for the `StrategyManager`.
    *   **`numpy`:**  Fundamental for numerical operations, especially when working with time-series data and indicator calculations in `talib`.
    *   **`peewee` and `peewee_async`:**  Object-Relational Mappers (ORMs) that simplify database interactions with TimescaleDB/PostgreSQL. `peewee_async` is critical for non-blocking, asynchronous database operations, essential for maintaining bot responsiveness.
    *   **`aiohttp`:**  An excellent asynchronous HTTP client, vital for interacting with REST APIs like DexScreener and Jupiter in a non-blocking manner.
    *   **`asyncio`:** Python's built-in asynchronous programming library, the foundation for building concurrent and efficient network applications like this trading bot.
    *   **`solana` and `solders`:** Solana-specific Python libraries for interacting with the Solana blockchain, including RPC and WebSocket communication, transaction construction, and key management. `solders` is a more recent and performant Solana library.
    *   **`loguru`:** Provides a user-friendly and feature-rich logging system, crucial for debugging, monitoring, and auditing the bot's operation.
*   **Rapid Prototyping and Development Speed:** Python's syntax is clear and concise, and its interpreted nature (though compiled just-in-time in many implementations) facilitates faster prototyping and iteration. For a project like a trading bot, where strategy adjustments and feature additions are frequent, rapid development is a significant advantage.
*   **Suitability for Testing and Simulation:** Python is very well-suited for backtesting and strategy simulation due to its data manipulation capabilities and scientific libraries. While the current bot doesn't have extensive backtesting implemented, Python lays the groundwork for easy integration of backtesting frameworks.
*   **Community Support and Resources:** Python has a massive and active community, meaning abundant online resources, tutorials, and readily available help when encountering issues. This is invaluable for both development and troubleshooting.
*   **Performance is "Good Enough" for This Application:** While Python might not be as lightning-fast as compiled languages, for the tasks involved in this bot – API requests, WebSocket handling, technical indicator calculations, and database interactions – Python with asynchronous programming and optimized libraries is performant *enough*.  The bottlenecks in trading bots are often more related to API rate limits, network latency, and blockchain confirmation times rather than pure execution speed of the code itself.  For a testnet meme coin bot, Python's performance is highly acceptable and prioritizes development speed and flexibility. If extreme high-frequency trading on mainnet were the goal, performance optimizations or a different language might become more critical.

In summary, Python was chosen as a pragmatic and effective language for this project, balancing performance requirements with the need for rapid development, access to essential libraries, and ease of use.

## Gotchas and Known Issues

*   **TA-Lib Installation on Windows:**  Installing `ta-lib` via `pip install ta-lib` on Windows often fails due to compilation issues.  **Solution:** The recommended approach for Windows is to download pre-built `ta-lib` `.whl` files from the unofficial GitHub releases page (search for "TA-Lib-wheel" on GitHub). Download the `.whl` file corresponding to your Python version and Windows architecture, and install it using `pip install <path_to_whl_file>`. *After* installing the `.whl`, you *might* need to install the Python wrapper using `pip install TA-Lib`.
*   **Meme Coin Scanner Log Parsing Assumptions:** The `MemeCoinScanner` relies on assumptions about the format of "TokenMinted" log messages. These assumptions are currently based on placeholders and are unlikely to match real-world Solana program log formats.  **Issue:**  The log parsing and coin detail extraction in `MemeCoinScanner` will almost certainly need to be significantly revised to work with actual Solana program logs that indicate new meme coin creation. You'll need to research and understand the specific programs or protocols involved in meme coin launches on Solana and their log output formats.
*   **Simplistic Meme Coin Filtering:** The `filter_coin` method in `MemeCoinScanner` uses extremely basic filtering criteria (checking for "MEME" in the symbol and a rudimentary liquidity proxy). **Issue:** This filtering is far too simplistic for real-world meme coin detection.  A production-ready meme coin scanner would need to incorporate much more advanced analysis to assess project legitimacy, smart contract security, community sentiment, on-chain metrics, and avoid rug pulls.
*   **Testnet Environment Focus:** The bot is configured and intended for the Solana Devnet. Trading on Devnet involves simulated tokens and is for testing purposes. **Caution:**  Adapting this bot for mainnet trading carries very significant financial risks.  Meme coins are highly volatile and susceptible to scams.  **Do not deploy this bot to mainnet without extensive testing, risk management strategies, and a thorough understanding of the code and market dynamics.**
*   **Error Handling and Robustness:** While error handling is included in various parts of the code (e.g., try-except blocks, logging errors),  a production-grade trading bot would require significantly more robust error handling, retry mechanisms, circuit breakers, and monitoring to ensure reliable operation and prevent unexpected behavior in edge cases.
*   **Strategy Simplification and Risk:** The provided trading strategy is a very basic example using common technical indicators. **Issue:** This strategy is not guaranteed to be profitable, especially in the highly volatile meme coin market.  Real-world trading strategies often involve far more complex models, risk management rules, and continuous optimization.  **Use this strategy as a starting point for experimentation and learning, not as a guaranteed path to profits.**

## How to Run the Solana Meme Coin Trading Bot: Step-by-Step

Before you begin, ensure you have:

*   **Python 3.8 or higher** installed.
*   **Poetry** installed for dependency management (installation instructions: [https://python-poetry.org/docs/#installation](https://python-poetry.org/docs/#installation)).
*   **TimescaleDB (PostgreSQL)** database set up and running. You'll need the connection string for this database.

**Steps:**

1.  **Clone the Repository (If you haven't already):**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Create and Configure the `.env` File:**
    *   Copy the `.env.example` file to `.env`:
        ```bash
        cp .env.example .env
        ```
    *   **Open the `.env` file and carefully configure the following environment variables:**

        ```dotenv
        WS_URL="wss://api.devnet.solana.com"             # Solana WebSocket endpoint (Devnet default)
        SOLANA_RPC_URL="https://api.devnet.solana.com"     # Solana RPC endpoint (Devnet default)
        TIMESCALE_DB_CONN_STR="postgresql://user:password@host:port/database" # Your TimescaleDB connection string
        TRENDING_API_ENDPOINT="https://api.dexscreener.com/token-boosts/top/v1" # DexScreener Trending API endpoint
        MEME_COIN_LIQUIDITY_THRESHOLD="20000"             # Liquidity threshold for meme coin scanning (USD)
        RECONNECT_DELAY="5"                                # Delay before reconnecting WebSocket (seconds)
        STRATEGY_LOOP_INTERVAL="5"                         # Interval for strategy loop execution (seconds)
        DEXSCREENER_POLL_INTERVAL="30"                     # Interval for polling DexScreener API (seconds)
        SECRET_KEY_B58="YOUR_SOLANA_PRIVATE_KEY_BASE58"   # Your Solana private key in Base58 format! **CRITICAL!**
        ORDER_QUANTITY="100"                               # Default order quantity (in SOL or meme coin units, context-dependent)
        SOL_MINT="So11111111111111111111111111111111111111112" # SOL mint address on Solana
        DEFAULT_MEME_MINT=""                              # Default meme coin mint for strategy loop (optional)
        JUPITER_API_KEY=""                                # Your Jupiter API key (optional)
        ```

        *   **`WS_URL`:**  The Solana WebSocket endpoint. For Devnet, the default is usually sufficient.
        *   **`SOLANA_RPC_URL`:** The Solana RPC endpoint. Devnet default is usually fine.
        *   **`TIMESCALE_DB_CONN_STR`:** **Crucially, you must replace the placeholder with your actual TimescaleDB connection string.** This string includes your database username, password, host, port, and database name. Ensure your database is accessible from where you run the bot.
        *   **`TRENDING_API_ENDPOINT`:**  DexScreener Trending API. The default is generally correct.
        *   **`MEME_COIN_LIQUIDITY_THRESHOLD`:**  Adjust this threshold as needed to control the liquidity level of meme coins the bot considers. Lower values will target coins with even lower liquidity.
        *   **`RECONNECT_DELAY`, `STRATEGY_LOOP_INTERVAL`, `DEXSCREENER_POLL_INTERVAL`:**  These control timing parameters. You can adjust these based on your desired responsiveness and resource usage.
        *   **`SECRET_KEY_B58`:**  **This is extremely important and security-sensitive!** You **MUST** replace `"YOUR_SOLANA_PRIVATE_KEY_BASE58"` with your **Solana private key in Base58 format.**
            *   **Generating a Keypair:** If you don't have a Solana keypair, use the provided `utils/keygen.py` script:
                ```bash
                python utils/keygen.py
                ```
                This script will generate a new keypair and print the private key in Base58 format and the public key. **Securely store the private key! Do not commit it to version control or share it insecurely.** **For testing, use a Devnet keypair!**
            *   **Important Security Note:**  **Treat your `SECRET_KEY_B58` like a highly sensitive password. Anyone who has it can control the Solana account associated with it.**
        *   **`ORDER_QUANTITY`:** The default quantity for buy/sell orders. The units depend on the context (SOL for SOL-based pairs, or meme coin units when trading meme coins).
        *   **`SOL_MINT`:**  The mint address for SOL on Solana. Should typically be the default value.
        *   **`DEFAULT_MEME_MINT`:**  Optionally, you can set a default meme coin mint address if you want the strategy loop to trade a specific meme coin instead of SOL. Leave it empty to trade SOL in the strategy loop.
        *   **`JUPITER_API_KEY`:**  Optional. If you have a Jupiter API key, you can add it here.

3.  **Install Python Dependencies using Poetry:**
    ```bash
    poetry install
    ```
    This command will read the `poetry.toml` file and install all necessary Python libraries, including `aiohttp`, `numpy`, `talib`, `solana`, `solders`, `peewee_async`, `loguru`, and `python-dotenv`.

4.  **Run the Trading Bot:**
    ```bash
    poetry run bot
    ```
    This command executes the `run_bot()` function defined in the `__main__` block of your Python script, which starts the bot.

5.  **Monitor the Bot and Logs:**
    *   The bot will output logs to the console (stdout) and also to the `trading_bot.log` file in the same directory.
    *   Review the logs to monitor the bot's activity, identify any errors, and observe its trading decisions.
    *   Check your TimescaleDB database to see if market data and trade logs are being stored correctly in the `market_data` and `trade_logs` tables.

**Important Considerations Before Running:**

*   **Testnet Operation (Recommended):**  Initially, run the bot exclusively on the Solana Devnet. Devnet uses simulated tokens, so you won't risk real funds. Verify that the bot connects to Devnet, fetches data, executes simulated trades, and logs data correctly before even considering using it on mainnet.
*   **Start with Small Order Quantities:** Begin with very small values for `ORDER_QUANTITY` to test the bot's execution and ensure you understand its behavior before increasing order sizes.
*   **Understand the Strategy:**  Thoroughly understand the implemented trading strategy. It is a simplified example and might not be consistently profitable. Backtest or paper trade extensively before risking real capital.
*   **Risk Management is Crucial:**  Automated trading carries inherent risks. Implement robust risk management strategies if you plan to use this bot for real trading (which is strongly discouraged for beginners, especially with meme coins). This could include setting stop-loss orders, position sizing limits, and carefully managing your capital allocation.
*   **Security Best Practices:** Protect your private key (`SECRET_KEY_B58`) meticulously. Never expose it publicly. Consider using environment variables securely and avoid hardcoding sensitive information directly in the code.
*   **Continuous Monitoring and Improvement:** Trading bots require ongoing monitoring and adjustments. Regularly review the logs, analyze trade performance, and be prepared to refine the strategy, parameters, and error handling as needed.

This detailed readme should provide a comprehensive understanding of the Solana Meme Coin Trading Bot, its features, architecture, setup, and important considerations for operation. Remember to use it responsibly and with caution, especially in live trading environments. Good luck!