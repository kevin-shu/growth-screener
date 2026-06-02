"""
Fallback data source: reconstruct daily price history from the
Ate329/top-us-stock-tickers GitHub repo, which auto-commits current S&P 500
prices every trading day via GitHub Actions.

Each commit captures NASDAQ "current price" (prev-day close) at ~12 UTC,
so commit_date maps to approximately the previous trading day's closing price.
"""

import io
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

_BASE = "https://raw.githubusercontent.com/Ate329/top-us-stock-tickers"
_FILE = "tickers/sp500.csv"

# All 115 commits from 2025-12-28 to 2026-06-01 (trading days)
COMMITS = [
    ("2026-06-01", "79657ef88efb151b78ab1aba6964e8e4dec1630e"),
    ("2026-05-29", "e75043c2e142672ff7765b183d9dbbb47cd4545f"),
    ("2026-05-28", "bb37e99dcb3f02ac3771671244e35916d472dfa0"),
    ("2026-05-27", "6620bf65fd8e95e02233ed8252fbb097a9424cbd"),
    ("2026-05-25", "f10b0e292787c01412e0f21485c6c7b194781c82"),
    ("2026-05-22", "08e822dbbbbb458ea852254c47e160f586f6bce0"),
    ("2026-05-21", "a9276d560a94d6a5505de691b0ed56212db1e787"),
    ("2026-05-20", "9187f9e2f5dedcf120d9030e590b9c4a9f7ae77b"),
    ("2026-05-19", "29adc52fb480d45d94d7f11dd022dbc084e890a9"),
    ("2026-05-18", "65f03b224db170868f7bd3fc944937f501e6bc7d"),
    ("2026-05-15", "990ba10c3bb48b6db50624ec79169562b5177320"),
    ("2026-05-14", "576274e01ec2f19ab6182716c2b2162dfbe50f82"),
    ("2026-05-13", "2ba35a25dc243cbb820309f70db556eeea4cc660"),
    ("2026-05-12", "906ef7bbd09098d561ca835d43fe940cb5859cbd"),
    ("2026-05-11", "b122a7f99a315e449fa79a965faa30f15147950a"),
    ("2026-05-08", "6a8b73085266241a01bc504628a0de6b5d575d3b"),
    ("2026-05-07", "635f6ff7d04c32d7ae98c59819acf7f1d83de4df"),
    ("2026-05-06", "eb720dfb8c5f899f29383a239f6a24621dff9a6b"),
    ("2026-05-05", "9cacdf80391d0bd2b8fbc3b9fe31ffc671544410"),
    ("2026-05-04", "61898cc49de4bd704de0196829a3cee3e4c3c528"),
    ("2026-05-01", "0781316d176a401c2d4f4d74e8813f6265c7335e"),
    ("2026-04-30", "54b8dcf5b498025a484e8f7be3041d647e9f6770"),
    ("2026-04-29", "cb19a5be421e243e3b5e8e79543812c6d54c2890"),
    ("2026-04-28", "cfa6b649dab55e8e94f2c51f3075a16d708e7a08"),
    ("2026-04-27", "e02c1708f237562a228a832bb70076c20eef6fbd"),
    ("2026-04-24", "85c8240b687eef9ecd4910e5730882e7069fe7aa"),
    ("2026-04-23", "a1fa79731af76c4343f65bcf0bdbda40e32cd755"),
    ("2026-04-22", "aa3c30f8cb4c2ecb6d429170b755d44b7b0ab4bb"),
    ("2026-04-21", "39e52996108f865b22fe77d5137ec8bb69aae3ed"),
    ("2026-04-20", "0c233841b0de143df50ec75612b5087ca472c714"),
    ("2026-04-17", "ea802e732fc30bf61d9d00fa106959123bc2f5c1"),
    ("2026-04-16", "e5803ecf6e1ff397515f4915172e10a37b9a8874"),
    ("2026-04-15", "999b46ad473ec7367bacfdffe89b48df029cf686"),
    ("2026-04-14", "adbf287adaa8838beded23ab8645c41f27e867f3"),
    ("2026-04-13", "25ade713bbc6bf98a24d3742989fc70ab99d02b0"),
    ("2026-04-10", "8cb967f0ef414ec9c5d1db4b6522b70de3b7f221"),
    ("2026-04-09", "d531720b3733a2c5af8ba83073cb039e88c39ab5"),
    ("2026-04-08", "3742dcb20ac93f60569c3e5112c1af30f68889b8"),
    ("2026-04-07", "4346b000da488c497d1fe27c15d4e4347f10b854"),
    ("2026-04-03", "648930c1e505bb09f1841491437f281f888c3d8e"),
    ("2026-04-02", "7d35b078493e5589e2e7cdbeac949f20dd9c3061"),
    ("2026-04-01", "b75469d0daa9ae8b38946413c380bb4a89069ec5"),
    ("2026-03-31", "6620bb3939d72e9d4c6522db74ee5af60cf7fc29"),
    ("2026-03-30", "29975583385401d91a4ddb92f830e857b6d467cc"),
    ("2026-03-27", "69b6a227cc6e0d357ce8b350fce55c249db36648"),
    ("2026-03-26", "243a6fa15dbdc83d398146253ec1d7e5aa67c430"),
    ("2026-03-25", "745f088212c54213f65bdeef53bc38ae23c4ed31"),
    ("2026-03-24", "994c10ce2df4869d4e6bbea00df530dce5587f66"),
    ("2026-03-23", "da650247bdbb834396d7ed97e8e2f5edc23b6160"),
    ("2026-03-20", "40617ce72e07b2ff9fa3def5290eac0ae42c2c"),
    ("2026-03-19", "3e9d6485681da53c538c0c8a87aa6a59b66c0746"),
    ("2026-03-18", "04ef5b540508f292fcece263f16fd9042484ab34"),
    ("2026-03-17", "31e62c84274af2a3184507873ca2ff7063b0c271"),
    ("2026-03-16", "c10bf114f6c911ade57ab5c0f385caed71e6a2f7"),
    ("2026-03-13", "f3524369f0a07aec834929df8c0e8dc48ecc605c"),
    ("2026-03-12", "69fd7b33bab7fd56ca7359c4888ed709f4060484"),
    ("2026-03-11", "390aac35ea1da00c1e3e5a23d8a9317fac05ef95"),
    ("2026-03-10", "59e274703d1b4cd21fa35ab89008b39d4bc2574a"),
    ("2026-03-09", "da6f20491f85893fb7861aef7eec1e894aa79e03"),
    ("2026-03-06", "02bb83e11650004148a3535dd57045992bc25adf"),
    ("2026-03-05", "0c1e391725583153e9d1f402081c3ab90def72ab"),
    ("2026-03-04", "f980e6a83b6dd8cbba477b9e550ad5bdf11f9c64"),
    ("2026-03-03", "6dedb439043e5f58da057dc8bb7151928ab51790"),
    ("2026-03-02", "11115049d7861c611b9e9e36fe00a1018c0dd8e7"),
    ("2026-02-27", "200bdb05ce08c08bbb81742bb18a47db7ff494fd"),
    ("2026-02-26", "94efdc6b85a1c526ac041fee159f3c764651f53e"),
    ("2026-02-25", "f8743f29815c6776eff8b6f54e3b146a3390e4d3"),
    ("2026-02-24", "e544276d98ad41ec423497b0f6d91532db5a7ad5"),
    ("2026-02-23", "8b05d717c2d3f54d6f3caa1b01f7779a9be5cb72"),
    ("2026-02-20", "c4bc188a33599ed9437bbe02a840b02f4392ea78"),
    ("2026-02-19", "b2f4710541bcae0d584c193bd72dbd15f573da32"),
    ("2026-02-18", "d5ba78b39dac68404ec088d5b9982c35e46974e7"),
    ("2026-02-16", "5d61e19d6f372d6cf574e6f1c32f0a20e92c191a"),
    ("2026-02-13", "43f9daa529bc06e43ef1c83e759fcbf37ff7cabc"),
    ("2026-02-12", "1575fac92cea0b6a8c7bc99d067a2b2718844126"),
    ("2026-02-11", "7b3fd2507abc74f3546297fd8d13a57602149719"),
    ("2026-02-10", "380bdfcc9043386befeb5b77aa2099d2b59fa517"),
    ("2026-02-09", "e6a4ebc7b8dc68d50fe09e970684945cb733ee5c"),
    ("2026-02-06", "247720023e12d030dccd13716fce7ed80155b621"),
    ("2026-02-05", "098dae88bcc96de24c13df536fad248d14e50af1"),
    ("2026-02-04", "398ef837b6c41a9be28462845b2e4ae9fb4bab98"),
    ("2026-02-03", "d6983a64e890d436e05191df94aba9b4a650aa1d"),
    ("2026-02-02", "8595b1d5af2620641e4aea7bf54c0f71194914fc"),
    ("2026-01-30", "3c62f9694b5b1f1d52db31f0f90407f1ec1b4878"),
    ("2026-01-29", "44ba2adf1afb07f72bb129f75982668b9d207c35"),
    ("2026-01-28", "129fb82a5c6f8d0f7f95956e081df5fa83aa81fc"),
    ("2026-01-27", "f6e8123c11307162f7cdbbb060fc0704f21f1ab9"),
    ("2026-01-26", "2ddb1175ea4651b0a523e0dee6edb810e7cfd328"),
    ("2026-01-23", "e83f2ae3f48a410dd9d2c9a3aa10f85293718f66"),
    ("2026-01-22", "9dd8524182e23a6922e4ea923385e2ae13f01a4d"),
    ("2026-01-21", "71c6db74acd8916273bca4463989b8b97941bea2"),
    ("2026-01-20", "cf723cae9fbe526a9f06deeb8fede492d04c7b13"),
    ("2026-01-19", "d0610b2d1af07a4ca1ef6b61f69bb4a16cc1091b"),
    ("2026-01-16", "81856b178c3599f786350ed03a59b2dd3eaeca4a"),
    ("2026-01-15", "c96f7ee5179f536decb5ccadb144821685eec027"),
    ("2026-01-14", "f09b59df5badfd30c75b7a0c0520ca93325393b2"),
    ("2026-01-13", "5e2a942b4cc36aaca9c70e75c5b4700fbe3ac02e"),
    ("2026-01-12", "a70f6ab16d59b267c7ffed71a691b64cc67246f2"),
    ("2026-01-09", "d05d9675898ebdf88b366e741f74b18f49037f8c"),
    ("2026-01-08", "dda216b20b83cd117531a31b409eb0d3e9bf3129"),
    ("2026-01-07", "62a56ead2bce85406a27dc0e4de7d01b25e8be79"),
    ("2026-01-06", "9ff866738e53f7dfa5161eae4be447519b0d8100"),
    ("2026-01-05", "7069adb3d1d3cb1aa473aa7e982161df3a6fd698"),
    ("2026-01-01", "ddbe263e2432cc6152235f3f928db4b787d2fe47"),
    ("2025-12-31", "d7d522b364ed0a1791ea1591a895344affe1d9f0"),
    ("2025-12-30", "88ef39c1cf6946a5c633cccbd4e14639bb76e637"),
    ("2025-12-28", "33c15d75e07133538b25818d146a72d80c3095d5"),
]

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; growth-screener/1.0)"}


_FALLBACK_FILE = "tickers/top_200.csv"


def _fetch_one(date_str: str, sha: str) -> tuple[str, dict] | None:
    """Download price CSV for one commit; tries sp500.csv then top_200.csv."""
    for fname in (_FILE, _FALLBACK_FILE):
        url = f"{_BASE}/{sha}/{fname}"
        try:
            r = requests.get(url, headers=_HEADERS, timeout=20)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                prices = df.set_index("symbol")["price"].to_dict()
                return (date_str, prices)
        except Exception:
            continue
    return None


def fetch_historical_github(
    max_workers: int = 20,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Download price history from Ate329/top-us-stock-tickers GitHub commits.
    Returns (close_df, volume_df) in the same format as fetch_historical().
    """
    rows = {}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_fetch_one, d, sha): d for d, sha in COMMITS
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                date_str, prices = result
                rows[date_str] = prices

    if not rows:
        return pd.DataFrame(), pd.DataFrame()

    close_df = pd.DataFrame(rows).T
    close_df.index = pd.to_datetime(close_df.index)
    close_df = close_df.sort_index()
    close_df = close_df.apply(pd.to_numeric, errors="coerce")

    # De-duplicate: if same date appears multiple times keep last row
    close_df = close_df[~close_df.index.duplicated(keep="last")]

    # Volume: synthesise from the latest sp500.csv (volume column exists there)
    volume_df = pd.DataFrame(1_000_000, index=close_df.index, columns=close_df.columns)

    return close_df, volume_df


def get_current_info() -> pd.DataFrame:
    """Return the latest sp500.csv snapshot for fundamental proxies."""
    date_str, sha = COMMITS[0]
    url = f"{_BASE}/{sha}/{_FILE}"
    try:
        r = requests.get(url, headers=_HEADERS, timeout=20)
        if r.status_code == 200:
            return pd.read_csv(io.StringIO(r.text))
    except Exception:
        pass
    return pd.DataFrame(columns=["symbol", "name", "price", "marketCap", "volume", "industry"])
