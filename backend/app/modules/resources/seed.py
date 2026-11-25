# DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
# Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
"""Resources demo seed data.

Generates a deterministic demo dataset:
    50 people + 5 crews + 30 equipment + 20 subcontractors = 105 resources
    25 skills + 15 certifications
    200 assignments across 8 weeks (mixed statuses)
    30 resource requests (mixed statuses)
    12 resource links (operator pairs)
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resources.models import (
    Assignment,
    AvailabilityWindow,
    Certification,
    Resource,
    ResourceLink,
    ResourceRequest,
    ResourceSkill,
    Skill,
)

_SEED = 42


def _make_resources(rng: random.Random) -> list[Resource]:
    resources: list[Resource] = []
    # 50 people
    first_names = [
        "Ana", "Bruno", "Carlos", "Daniela", "Eduardo", "Fernanda", "Gabriel",
        "Helena", "Igor", "Juliana", "Kaique", "Larissa", "Marcos", "Natália",
        "Otávio", "Patrícia", "Queila", "Rafael", "Sofia", "Tiago", "Úrsula",
        "Vinícius", "William", "Ximena", "Yasmin", "Zeca",
    ]
    last_names = [
        "Silva", "Santos", "Oliveira", "Souza", "Costa", "Pereira",
        "Almeida", "Ferreira", "Rodrigues", "Lima",
    ]
    for i in range(50):
        fn = first_names[i % len(first_names)]
        ln = last_names[i % len(last_names)]
        resources.append(
            Resource(
                code=f"P-{i + 1:03d}",
                name=f"{fn} {ln}",
                resource_type="person",
                default_cost_rate=Decimal(str(35 + rng.randint(0, 60))),
                currency="BRL",
                # One full-time person can absorb 100% per bucket.
                capacity_percent=100,
                status="active" if rng.random() > 0.05 else "on_leave",
            )
        )
    # 5 crews
    for i in range(5):
        resources.append(
            Resource(
                code=f"C-{i + 1:03d}",
                name=f"Equipe {chr(65 + i)}",
                resource_type="crew",
                default_cost_rate=Decimal(str(150 + rng.randint(0, 100))),
                currency="BRL",
                # A multi-member crew can split across up to three sites.
                capacity_percent=300,
                status="active",
            )
        )
    # 30 equipment
    eq_kinds = ["Escavadeira", "Guindaste", "Pá carregadeira", "Betoneira", "Caminhão basculante"]
    for i in range(30):
        kind = eq_kinds[i % len(eq_kinds)]
        resources.append(
            Resource(
                code=f"E-{i + 1:03d}",
                name=f"{kind} #{i + 1}",
                resource_type="equipment",
                default_cost_rate=Decimal(str(80 + rng.randint(0, 200))),
                currency="BRL",
                # A single machine works one place at a time.
                capacity_percent=100,
                status="active" if rng.random() > 0.1 else "inactive",
            )
        )
    # 20 subcontractors. Capacity is deliberately left unset (None) for subs:
    # an external company's headcount is not tracked in our resource model, so
    # leveling honestly reports their buckets as "capacity unknown" rather than
    # fabricating a ceiling. This also exercises the unknown-capacity path in
    # the demo dataset.
    for i in range(20):
        resources.append(
            Resource(
                code=f"S-{i + 1:03d}",
                name=f"Subcontratada {chr(65 + (i % 26))}{i + 1} Ltda.",
                resource_type="subcontractor",
                default_cost_rate=Decimal(str(200 + rng.randint(0, 500))),
                currency="BRL",
                status="active",
            )
        )
    return resources


def _make_skills() -> list[Skill]:
    return [
        Skill(code="trade.carpentry", name="Carpintaria", category="trade"),
        Skill(code="trade.masonry", name="Alvenaria", category="trade"),
        Skill(code="trade.concrete", name="Concretagem", category="trade"),
        Skill(code="trade.steelwork", name="Estruturas metálicas", category="trade"),
        Skill(code="trade.welding", name="Soldagem", category="trade"),
        Skill(code="trade.plumbing", name="Instalações hidráulicas", category="trade"),
        Skill(code="trade.electrical", name="Instalações elétricas", category="trade"),
        Skill(code="trade.hvac", name="Climatização", category="trade"),
        Skill(code="trade.roofing", name="Cobertura", category="trade"),
        Skill(code="trade.tiling", name="Assentamento de revestimentos", category="trade"),
        Skill(code="trade.plastering", name="Reboco", category="trade"),
        Skill(code="trade.painting", name="Pintura", category="trade"),
        Skill(code="trade.scaffolding", name="Montagem de andaimes", category="trade"),
        Skill(code="trade.glazing", name="Vidraçaria", category="trade"),
        Skill(code="cert.crane_op", name="Operador de guindaste", category="certification"),
        Skill(code="cert.excavator_op", name="Operador de escavadeira", category="certification"),
        Skill(code="cert.first_aid", name="Primeiros socorros", category="certification"),
        Skill(code="cert.scaffolding_inspector", name="Inspetor de andaimes", category="certification"),
        Skill(code="cert.confined_space", name="Entrada em espaço confinado", category="certification"),
        Skill(code="lang.en", name="Inglês", category="language"),
        Skill(code="lang.de", name="Alemão", category="language"),
        Skill(code="lang.es", name="Espanhol", category="language"),
        Skill(code="lang.ru", name="Russo", category="language"),
        Skill(code="lang.it", name="Italiano", category="language"),
        Skill(code="other.gps_surveying", name="Levantamento com GPS", category="other"),
    ]


def _make_certifications(rng: random.Random, resources: Sequence[Resource]) -> list[Certification]:
    """15 certifications spread across persons."""
    persons = [r for r in resources if r.resource_type == "person"]
    cert_types = [
        "Operador de guindaste",
        "Operador de escavadeira",
        "Primeiros socorros",
        "Soldagem classe A",
        "Inspetor de andaimes",
        "Entrada em espaço confinado",
        "Operador de empilhadeira",
        "Trabalho em altura",
        "Permissão para trabalho a quente",
    ]
    out: list[Certification] = []
    for i in range(15):
        person = persons[i % len(persons)]
        issued = datetime.now(UTC).date() - timedelta(days=rng.randint(30, 1200))
        valid_for_days = rng.choice([365, 730, 1095])  # 1y/2y/3y
        valid_until = issued + timedelta(days=valid_for_days)
        out.append(
            Certification(
                resource_id=person.id,
                cert_type=cert_types[i % len(cert_types)],
                cert_number=f"CERT-{1000 + i}",
                issued_by="Autoridade local",
                issue_date=issued.isoformat(),
                valid_until=valid_until.isoformat(),
                status="valid" if valid_until >= datetime.now(UTC).date() else "expired",
            )
        )
    return out


def _make_assignments(
    rng: random.Random,
    resources: Sequence[Resource],
    project_ids: Sequence[uuid.UUID],
) -> list[Assignment]:
    """200 assignments over 8 weeks across given projects."""
    if not project_ids:
        return []
    out: list[Assignment] = []
    base = datetime.now(UTC).replace(hour=8, minute=0, second=0, microsecond=0)
    statuses = ["proposed", "confirmed", "in_progress", "completed", "cancelled"]
    weights = [10, 50, 20, 15, 5]
    for i in range(200):
        r = resources[rng.randint(0, len(resources) - 1)]
        proj = project_ids[rng.randint(0, len(project_ids) - 1)]
        day_offset = rng.randint(-7, 49)  # ±8 weeks
        duration_days = rng.choice([1, 2, 3, 5, 7, 10, 14])
        start = base + timedelta(days=day_offset)
        end = start + timedelta(days=duration_days)
        out.append(
            Assignment(
                resource_id=r.id,
                project_id=proj,
                start_at=start,
                end_at=end,
                allocation_percent=rng.choice([25, 50, 75, 100]),
                status=rng.choices(statuses, weights=weights, k=1)[0],
                cost_rate=r.default_cost_rate,
                currency=r.currency or "BRL",
            )
        )
    return out


def _make_requests(
    rng: random.Random,
    project_ids: Sequence[uuid.UUID],
    skills: Sequence[Skill],
) -> list[ResourceRequest]:
    if not project_ids:
        return []
    out: list[ResourceRequest] = []
    base = datetime.now(UTC).replace(hour=8, minute=0, second=0, microsecond=0)
    statuses = ["open", "fulfilled", "cancelled"]
    weights = [60, 30, 10]
    priorities = ["low", "med", "high", "critical"]
    titles = [
        "Carpinteiro para formas",
        "Operador de guindaste na próxima semana",
        "Pedreiros adicionais",
        "Soldador para estrutura metálica",
        "Montador de andaimes",
        "Trabalhador treinado em primeiros socorros",
        "Operador de escavadeira",
        "Pintores para acabamentos",
    ]
    for i in range(30):
        proj = project_ids[rng.randint(0, len(project_ids) - 1)]
        day_offset = rng.randint(0, 30)
        duration = rng.randint(1, 14)
        start = base + timedelta(days=day_offset)
        end = start + timedelta(days=duration)
        req_skills = rng.sample(
            [s.id for s in skills],
            k=min(rng.randint(1, 3), len(skills)),
        )
        out.append(
            ResourceRequest(
                project_id=proj,
                title=titles[i % len(titles)],
                description=f"Profissional necessário no canteiro por {duration} dias a partir de {start:%d/%m/%Y}.",
                required_skills=[str(s) for s in req_skills],
                start_at=start,
                end_at=end,
                quantity=rng.randint(1, 4),
                priority=rng.choice(priorities),
                status=rng.choices(statuses, weights=weights, k=1)[0],
            )
        )
    return out


def _make_links(rng: random.Random, resources: Sequence[Resource]) -> list[ResourceLink]:
    persons = [r for r in resources if r.resource_type == "person"]
    equipment = [r for r in resources if r.resource_type == "equipment"]
    out: list[ResourceLink] = []
    if not persons or not equipment:
        return out
    # 12 operator pairs: person <-> equipment
    for _ in range(12):
        p = persons[rng.randint(0, len(persons) - 1)]
        e = equipment[rng.randint(0, len(equipment) - 1)]
        out.append(
            ResourceLink(
                primary_resource_id=e.id,
                secondary_resource_id=p.id,
                link_type="operator",
                notes="Operador designado",
            )
        )
    return out


async def seed_resources_demo(
    session: AsyncSession,
    project_ids: Sequence[uuid.UUID],
) -> dict[str, int]:
    """Insert a deterministic resources demo dataset.

    Args:
        session: Async DB session.
        project_ids: Project IDs to spread assignments / requests over.

    Returns:
        Dict with per-table insert counts.
    """
    # O código estável identifica uma instalação anterior; não recriar recursos
    # nem suas relações, inclusive se o usuário editou os registros depois.
    existing = (await session.execute(select(Resource.id).where(Resource.code == "P-001").limit(1))).first()
    if existing is not None:
        return {
            "resources": 0, "skills": 0, "resource_skills": 0,
            "certifications": 0, "availability_windows": 0,
            "assignments": 0, "requests": 0, "links": 0,
        }
    rng = random.Random(_SEED)

    resources = _make_resources(rng)
    for r in resources:
        session.add(r)
    await session.flush()

    skills = _make_skills()
    for s in skills:
        session.add(s)
    await session.flush()

    # Random skill attachments: each person gets 2-5 skills
    persons = [r for r in resources if r.resource_type == "person"]
    rs_count = 0
    for p in persons:
        chosen = rng.sample(skills, k=min(rng.randint(2, 5), len(skills)))
        for s in chosen:
            session.add(
                ResourceSkill(
                    resource_id=p.id,
                    skill_id=s.id,
                    level=rng.choice(["basic", "competent", "expert"]),
                )
            )
            rs_count += 1
    await session.flush()

    certs = _make_certifications(rng, resources)
    for c in certs:
        session.add(c)
    await session.flush()

    # Each person gets a normal-hours availability window for next 30 days
    base = datetime.now(UTC).replace(hour=8, minute=0, second=0, microsecond=0)
    win_count = 0
    for p in persons[:20]:  # subset to keep dataset light
        session.add(
            AvailabilityWindow(
                resource_id=p.id,
                window_type="available",
                start_at=base,
                end_at=base + timedelta(days=30),
                note="Jornada de trabalho padrão",
            )
        )
        win_count += 1
    await session.flush()

    assignments = _make_assignments(rng, resources, project_ids)
    for a in assignments:
        session.add(a)
    await session.flush()

    requests = _make_requests(rng, project_ids, skills)
    for q in requests:
        session.add(q)
    await session.flush()

    links = _make_links(rng, resources)
    for k in links:
        session.add(k)
    await session.flush()

    return {
        "resources": len(resources),
        "skills": len(skills),
        "resource_skills": rs_count,
        "certifications": len(certs),
        "availability_windows": win_count,
        "assignments": len(assignments),
        "requests": len(requests),
        "links": len(links),
    }
