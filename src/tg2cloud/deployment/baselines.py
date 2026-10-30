"""Reviewed historical payload identities, shipped with the trusted helper.

This is a compatibility allowlist, not a signature or an operator override.
Downloaded historical Python is never imported to discover its identity.
"""
from __future__ import annotations

import hashlib

from tg2cloud.deployment.payload import payload_sources
from tg2cloud.deployment.profiles import PRODUCTS

CATALOG = {
    "v1.5.4": {
        "commit": "7d3a56ff3cb7b9d9f8d994930904c1749677c69b",
        "payloads": {
            "clouddrive2": "608129c305f2e0e86fd5e5e961667b83ad3d620148c3ff4dbfae4d0d8fdaef5c",
            "openlist": "e862ae992233d67a36754114bb70c0ff5167f7af090138fb6955a7c9fcdd3d68",
        },
    },
    "v1.5.3": {
        "commit": "2e6f06f09e1e2ac9fe8ae2d9c6e1d83cc7a3bee1",
        "payloads": {
            "clouddrive2": "6a1699e92d763c0b9a8c160b80d440d2d697c1cd9e43c127eba6522de6435419",
            "openlist": "2667d0340dc384df8e3720e244648340199ad1dba371e7b85fc58e331708e0d9",
        },
    },
    "v1.5.2": {'commit': 'dc02d879cc44ee6bbf1f858ea383ede2ea71022b', 'payloads': {'clouddrive2': '995125031e80a1e759e383bbeab7865394c610735f3d094bd060be0d3aaa1fb0', 'openlist': '6484569ca4246ec24768b29501d957fcbc5126bf148aa1ec6168793a124908c5'}},
    "v1.5.1": {'commit': '2741c6b5f40469a2bc035c87274b62fc66ef1a74', 'payloads': {'clouddrive2': '65e2dd5a4c5e1914cde24729d0db92153ff6302294127f99d9abd59990948dc2', 'openlist': '813ac6cccc0237069e555a86f91ae987f015f50114ef79c5a3b35b4962125a2f'}},
    "v1.5.0": {
        "commit": "eb635967d22bdc8d7c7467b6a6e3b7812ab8fa56",
        "payloads": {
            "clouddrive2": "97e8fb662c8cfc5790b29a6dcda61c5fd00566e73dbb9e93b86b7f01f6586712",
            "openlist": "bc5f5b9a2d2d87ad9cad8649b50ddd33d2e0d1fe380fa312a635d24709996583"
        }
    },
    "v1.4.11": {
        "commit": "715999fd1fa64077172df6e43b78c3ab8bd2f7c2",
        "payloads": {
            "clouddrive2": "4e32c01e1f12545858fe72610923ab0e9079b592f148eb05266c7ab86be9ff62",
            "openlist": "004a2841747fe007c47126aa4ad00449b0ae40bf000eac2395a09e7f8e5e2351"
        }
    },
    "v1.4.10": {
        "commit": "39386ce8c4901727362e7d22ff4676922ad25052",
        "payloads": {
            "clouddrive2": "1a5fe31d931a754d5b60cce482aae9793a2142b35e589c1aae6ae5aa6b312442",
            "openlist": "d3f0ce3b71bc7f3e405b358b468b4c7f1629b24406c7fb2cffb3052b7a70c202"
        }
    },
    "v1.4.9": {
        "commit": "8a2f7a1be42c1f229530cde16f5fa63650a0c17a",
        "payloads": {
            "clouddrive2": "828be197266ff0b7e29e88cff0edb1876ca0d7971bff70a451e2e7cfe692dafe",
            "openlist": "52b6758166f33c7075430bdf5aae89a1216919279e5abd25e811eeac48c86717",
        },
    },
    "v1.4.8": {
        "commit": "e24cddfa77fe76b90ea63ee9e7d88008066cb0a3",
        "payloads": {
            "clouddrive2": "416411acfa25282da91dc98382c05a02cf38142b0b4bcea502091db814ea8f45",
            "openlist": "eeec8636345d731314761cb7ae974418d934a1cec6e0921019b4f6ff3af3cb43",
        },
    },
    "v1.3.4": {
        "commit": "ef35d133a9e25572ff5f8363819d5c8e8984e74c",
        "payloads": {
            "clouddrive2": "2f560dbc5b4ebeabb4b2ebf3a1729bd57e9c152c60fe40567e1fe0daa98c211e",
            "openlist": "47e37f326e3ca23060c5d78935ef77acd00cde1f6bbb1f440d2c7dcac8bb612d",
        },
    },
    "v1.4.0": {
        "commit": "8bd4cf1fd7180f31579f5fe702d2c2d07c3b13f8",
        "payloads": {
            "clouddrive2": "179efd2ade423282df244c87fb8a3e7b6a72a7a578acf336eba935e13fb8843b",
            "openlist": "abd0667c4f5d5517a52af2a0fd8d8c6579d55aea9dd6b2c9c2a25cbfbc47b971",
        },
    },
    "v1.4.1": {
        "commit": "dde550bc7fa6047ddcc945ef82131962611fec05",
        "payloads": {
            "clouddrive2": "9ffefb84b62ecca95f48e882a43fd0f094f2c43138d528725fa09289b1839619",
            "openlist": "358227fddc3f452cb79b2dde812bba78e12ed2a052432cb12ae5a6e0d13a7e85",
        },
    },
    "v1.4.2": {
        "commit": "42e2c372823a085c36a7a7597ce775441598aaf9",
        "payloads": {
            "clouddrive2": "81946a7f106e0a551bb29365b4dda1817823e41f06aa67c3fe1c86759027cfbe",
            "openlist": "248e1aa8a273b96d65aa6e8dcb6cd7c312c213371f5ef3e3282973694cb9e1fc",
        },
    },
    "v1.4.3": {
        "commit": "5aaf6a9b158d785ffa2fee52750c022fb8654810",
        "payloads": {
            "clouddrive2": "368cd7285e4abc9655ea84fdb857dc657b0b2aa4cebeeabca02c028a7ca59532",
            "openlist": "2f901b9fdcb700dd528d9cf173e5376bafa77847514ee28d11705ac83e1e3b33",
        },
    },
    "v1.4.4": {
        "commit": "6164a237108786c01a7a958ab56e16023df04d79",
        "payloads": {
            "clouddrive2": "e89c739f5c8e16d739a954b2c41b184e4fc8fbcacea4b60047ca50b06291d10b",
            "openlist": "a53178080a51948df03a795e3779686ec4c88f42b57f98f6d1a46908f4f3e44a",
        },
    },
    "v1.4.5": {
        "commit": "cd9b13722752b1f1663c5ba4cbb91b7c21c7f882",
        "payloads": {
            "clouddrive2": "2937ff6b41c199ae9fa19b5d19f9bf48706426a6e8ec19ff45566c1fc5073ef1",
            "openlist": "2718576bbc3f38000237c66840b6d80abe3d50d54637f00a1f9e2bb04e2dafb0",
        },
    },
    "v1.4.6": {
        "commit": "2e18eba718df83beec3a9d0784ca8037125bdd20",
        "payloads": {
            "clouddrive2": "d6b242a03e7028b5b7e3a21911e5bd6f74d20c0244200b45171ca0e8e6b1bf57",
            "openlist": "086b20a63e224d5af8134f929897a0af1b4ece55e57fbff8205ccd4e12d4de93",
        },
    },
    "v1.4.7": {
        "commit": "322ae065d6cb6a7330f78b8cc0ee60c4c3c53cdb",
        "payloads": {
            "clouddrive2": "57693670bd88c2ad5dda1aec5ba9630152c45de388f1fa0c121e6e944662ffe3",
            "openlist": "a0d87166b9c1ecd23edcb24b65fcac00878c5bf4803ee25e5386d3904312cc98",
        },
    },
}


def payload_digest(source, product) -> str:
    records = []
    for name, path in sorted(payload_sources(source, product, strict=False).items()):
        digest = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        records.append(f"{digest}  {name}\n")
    return hashlib.sha256("".join(records).encode("utf-8")).hexdigest()


def verify(source, tag: str, commit: str) -> None:
    record = CATALOG.get(tag)
    if not record or record["commit"] != commit or set(record["payloads"]) != set(PRODUCTS):
        raise ValueError("历史基线不在本版可信目录中；停止，不接受任意提交")
    for key, product in PRODUCTS.items():
        if payload_digest(source, product) != record["payloads"][key]:
            raise ValueError("历史基线载荷清单不匹配；停止，不覆盖实例")
