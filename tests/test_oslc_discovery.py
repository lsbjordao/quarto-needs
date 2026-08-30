from __future__ import annotations

import pytest

from quarto_needs.oslc_rm import OSLC_CORE_NS, OSLC_RM_NS, discover_rm_services


def _ref(uri: str) -> dict[str, str]:
    return {"@id": uri}


def test_discovery_selects_only_rm_services_and_query_capabilities() -> None:
    provider = {
        f"{OSLC_CORE_NS}service": [
            {
                "@id": "https://provider.test/oslc/service/rm",
                f"{OSLC_CORE_NS}domain": [_ref(OSLC_RM_NS)],
                f"{OSLC_CORE_NS}queryCapability": [
                    {
                        f"{OSLC_CORE_NS}queryBase": [
                            _ref("https://provider.test/oslc/rm/requirements")
                        ],
                        f"{OSLC_CORE_NS}resourceShape": [
                            _ref("https://provider.test/oslc/shapes/requirement")
                        ],
                        f"{OSLC_CORE_NS}resourceType": [
                            _ref(f"{OSLC_RM_NS}Requirement")
                        ],
                    }
                ],
            },
            {
                "@id": "https://provider.test/oslc/service/change",
                f"{OSLC_CORE_NS}domain": [
                    _ref("http://open-services.net/ns/cm#")
                ],
            },
        ]
    }

    services = discover_rm_services(provider)

    assert len(services) == 1
    assert services[0].service_uri == "https://provider.test/oslc/service/rm"
    assert len(services[0].query_capabilities) == 1
    query = services[0].query_capabilities[0]
    assert query.query_base_uri == "https://provider.test/oslc/rm/requirements"
    assert query.resource_shape_uri == "https://provider.test/oslc/shapes/requirement"
    assert query.resource_types == (f"{OSLC_RM_NS}Requirement",)


def test_discovery_requires_exactly_one_query_base() -> None:
    provider = {
        f"{OSLC_CORE_NS}service": [
            {
                f"{OSLC_CORE_NS}domain": [_ref(OSLC_RM_NS)],
                f"{OSLC_CORE_NS}queryCapability": [{}],
            }
        ]
    }

    with pytest.raises(ValueError, match="exactly one oslc:queryBase"):
        discover_rm_services(provider)


def test_discovery_rejects_multiple_resource_shapes() -> None:
    provider = {
        f"{OSLC_CORE_NS}service": [
            {
                f"{OSLC_CORE_NS}domain": [_ref(OSLC_RM_NS)],
                f"{OSLC_CORE_NS}queryCapability": [
                    {
                        f"{OSLC_CORE_NS}queryBase": [
                            _ref("https://provider.test/oslc/rm/requirements")
                        ],
                        f"{OSLC_CORE_NS}resourceShape": [
                            _ref("https://provider.test/oslc/shapes/a"),
                            _ref("https://provider.test/oslc/shapes/b"),
                        ],
                    }
                ],
            }
        ]
    }

    with pytest.raises(ValueError, match="at most one oslc:resourceShape"):
        discover_rm_services(provider)


def test_discovery_is_deterministic_by_service_and_query_base() -> None:
    provider = {
        f"{OSLC_CORE_NS}service": [
            {
                "@id": "https://provider.test/oslc/service/z",
                f"{OSLC_CORE_NS}domain": [_ref(OSLC_RM_NS)],
                f"{OSLC_CORE_NS}queryCapability": [
                    {
                        f"{OSLC_CORE_NS}queryBase": [
                            _ref("https://provider.test/oslc/query/z")
                        ]
                    }
                ],
            },
            {
                "@id": "https://provider.test/oslc/service/a",
                f"{OSLC_CORE_NS}domain": [_ref(OSLC_RM_NS)],
                f"{OSLC_CORE_NS}queryCapability": [
                    {
                        f"{OSLC_CORE_NS}queryBase": [
                            _ref("https://provider.test/oslc/query/b")
                        ]
                    },
                    {
                        f"{OSLC_CORE_NS}queryBase": [
                            _ref("https://provider.test/oslc/query/a")
                        ]
                    },
                ],
            },
        ]
    }

    services = discover_rm_services(provider)
    assert [service.service_uri for service in services] == [
        "https://provider.test/oslc/service/a",
        "https://provider.test/oslc/service/z",
    ]
    assert [
        query.query_base_uri for query in services[0].query_capabilities
    ] == [
        "https://provider.test/oslc/query/a",
        "https://provider.test/oslc/query/b",
    ]
