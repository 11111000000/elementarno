"""Command line interface for the ЭЛЕМЕНТАРНО engine."""

import argparse
import json
import re
import sys
from pathlib import Path

from . import config as cfg
from .diff import diff_scenes
from .ledger import Verdict, score_hypotheses, validate
from .ledger import verdict as decide_verdict
from .providers import enrich, load_providers
from .puzzle import build_claims, load_puzzle, solve
from .render import render
from .rules import evaluate_all, load_packs
from .scene import validate_scene

DEFAULT_RULES_DIR = "rules"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(data):
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False))


def selected_rules(rules_dir, packs, profile=None):
    rules = load_packs(rules_dir)
    if not packs and profile:
        packs = profile.get("packs")
    if not packs:
        return rules
    wanted = set(packs)
    return [rule for rule in rules if rule.pack in wanted]


def profile_for(args):
    """Профиль из --config/--profile: пакеты, режим, персона, пороги."""
    try:
        config = cfg.load_config(args.config)
        return cfg.get_profile(config, getattr(args, "profile", None))
    except (FileNotFoundError, KeyError):
        return None


def apply_profile(args, profile=None):
    """Подставить профиль в аргументы команды.

    Явно заданный флаг всегда сильнее профиля: иначе `--min-findings 1`
    молча терялся рядом с `--profile`, и команды решали разные задачи по
    разным правилам. Профиль задаёт значение только там, где флаг не задан.
    """
    profile = profile if profile is not None else profile_for(args)
    if profile:
        args.pack = args.pack or profile.get("packs")
        if getattr(args, "mode", None) == "detective":
            args.mode = profile.get("mode", args.mode)
        if getattr(args, "persona", None) == "plain":
            args.persona = profile.get("persona") or args.persona
        if getattr(args, "min_findings", None) is None:
            args.min_findings = profile.get("min_findings", 1)
    if getattr(args, "min_findings", None) is None:
        args.min_findings = 1
    return profile


def cmd_check(args):
    problems = validate_scene(load_json(args.scene))
    rules = load_packs(args.rules)
    seen = set()
    for rule in rules:
        if rule.id in seen:
            problems.append({"code": "duplicate_rule", "detail": rule.id})
        seen.add(rule.id)
        for dep in rule.depends_on:
            if dep not in seen and dep not in {r.id for r in rules}:
                problems.append({"code": "missing_dependency", "detail": f"{rule.id} -> {dep}"})
    if problems:
        for problem in problems:
            print(f"  ✗ {problem['code']}: {problem['detail']}", file=sys.stderr)
        print(f"проблем: {len(problems)}", file=sys.stderr)
        return 1
    print(f"сцена корректна; правил загружено: {len(rules)}")
    return 0


def cmd_findings(args):
    scene = load_json(args.scene)
    rules = selected_rules(args.rules, args.pack)
    findings = evaluate_all(rules, scene)
    if args.json:
        dump(findings)
        return 0
    if not findings:
        print("улик не найдено")
        return 0
    for finding in findings:
        flag = " (черновик)" if finding["provisional"] else ""
        print(f"[{finding['rule_id']}]{flag} {finding['title']} — уверенность ≤ {finding['confidence_ceiling']:.2f}")
        print(f"    {finding['inference']}")
        print(f"    якоря: {finding['anchors'] or '—'}")
        for source in finding["sources"]:
            print(f"    источник: {source['ref']} {source.get('note', '')}")
    return 0


def cmd_diff(args):
    changes = diff_scenes(load_json(args.before), load_json(args.after))
    if args.json:
        dump(changes)
        return 0
    if not changes:
        print("различий не найдено")
        return 0
    for change in changes:
        print(f"- {change['kind']}: {json.dumps({k: v for k, v in change.items() if k != 'kind'}, ensure_ascii=False)}")
    return 0


def _ledger_for(scene, findings, ledger_path):
    if ledger_path:
        return load_json(ledger_path)
    return {"claims": build_claims(findings), "hypotheses": []}


def _annotate_profile_gaps(report, all_rules, selected_rules):
    """Отличить опечатку в ссылке от правила, не вошедшего в профиль.

    Профиль задаёт доменный охват, и ссылка на правило вне профиля — это
    не ошибка ссылки, а иной диагноз: либо сменить профиль, либо убрать
    утверждение. Без подсказки агент ищет опечатку там, где её нет.
    """
    known = {rule.id for rule in all_rules}
    in_scope = {rule.id for rule in selected_rules}
    for error in report.get("errors", []):
        if error.get("code") != "unresolved_citation":
            continue
        outside = []
        for finding_id in re.findall(r"F-([A-Z]+-\d+)", error.get("detail", "")):
            if finding_id in known and finding_id not in in_scope:
                outside.append(finding_id)
        if outside:
            packs = ", ".join(sorted({rule.pack for rule in selected_rules}))
            error["hint"] = (f"правило {', '.join(outside)} есть в базе, но не входит в профиль "
                             f"(паки: {packs}). Смените профиль или уберите утверждение")


def cmd_verify(args):
    apply_profile(args)
    scene = load_json(args.scene)
    rules = selected_rules(args.rules, args.pack)
    findings = evaluate_all(rules, scene)
    ledger = _ledger_for(scene, findings, args.ledger)
    report = validate(findings, ledger)
    _annotate_profile_gaps(report, load_packs(args.rules), rules)
    if args.json:
        dump(report)
    else:
        for error in report["errors"]:
            print(f"  ✗ {error.get('claim_id') or error.get('hypothesis_id')}: {error['code']} — {error['detail']}")
            if error.get("hint"):
                print(f"      {error['hint']}")
        print(f"полнота цитат: {report['citation_completeness']:.2f} "
              f"({report['resolvable_claims']}/{report['claims']})")
    return 1 if report["errors"] else 0


def cmd_tell(args):
    apply_profile(args)
    scene = load_json(args.scene)
    rules = selected_rules(args.rules, args.pack)
    findings = evaluate_all(rules, scene)
    ledger = _ledger_for(scene, findings, args.ledger)
    report = validate(findings, ledger)
    usable_claims = []
    for claim in ledger.get("claims", []):
        if any(error.get("claim_id") == claim["claim_id"] for error in report["errors"]):
            continue
        usable_claims.append(claim)
    hypotheses = score_hypotheses(findings, usable_claims, ledger.get("hypotheses", []))
    state = decide_verdict(findings, usable_claims, args.min_findings, args.mode)
    print(render(args.mode, findings, usable_claims, hypotheses, state, args.persona, report))
    return 0


def cmd_board(args):
    from .board import build
    from .nextshot import discriminator_questions

    apply_profile(args)
    scene = load_json(args.scene)
    rules = selected_rules(args.rules, args.pack)
    findings = evaluate_all(rules, scene)
    ledger = _ledger_for(scene, findings, args.ledger)
    report = validate(findings, ledger)
    usable_claims = []
    for claim in ledger.get("claims", []):
        if any(error.get("claim_id") == claim["claim_id"] for error in report["errors"]):
            continue
        usable_claims.append(claim)
    hypotheses = score_hypotheses(findings, usable_claims, ledger.get("hypotheses", []))
    state = decide_verdict(findings, usable_claims, args.min_findings, args.mode)
    questions = discriminator_questions(hypotheses)

    scene_path = Path(args.scene)
    ledger_path = Path(args.ledger) if args.ledger else None
    commands = [
        f"python3 -m tools.elementarno.cli verify {scene_path} --ledger {ledger_path or 'ledger.json'}",
        f"python3 -m tools.elementarno.cli tell {scene_path} --ledger {ledger_path or 'ledger.json'} --persona {args.persona}",
        f"python3 -m tools.elementarno.cli nextshot {scene_path} --hypotheses {ledger_path or 'ledger.json'}",
        f"python3 -m tools.elementarno.cli board {scene_path} --ledger {ledger_path or 'ledger.json'} --out {args.out}",
    ]

    title = args.title or f"Доска разбора: {scene_path.stem}"
    subtitle = args.subtitle or (
        f"Кадр {scene.get('meta', {}).get('image_id', scene_path.stem)}; "
        f"улик — {len(findings)}, утверждений — {len(usable_claims)}, версий — {len(hypotheses)}."
    )
    verdict_text = {
        "sufficient_evidence": "улик достаточно",
        "insufficient_evidence": "улик недостаточно",
        "conflicting_evidence": "улики противоречат друг другу",
    }.get(getattr(state, "value", str(state)), str(state))
    badges = [
        ("вердикт", verdict_text),
        ("улик", str(len(findings))),
        ("утверждений", str(len(usable_claims))),
        ("версий", str(len(hypotheses))),
        ("ошибок протокола", str(len(report["errors"]))),
        ("различающих вопросов", str(len(questions))),
    ]
    meta = {"badges": badges, "tone": "warn" if report["errors"] else "good"}

    html_doc = build(
        scene,
        findings,
        ledger,
        hypotheses=hypotheses,
        questions=questions,
        verdict=state,
        narrative=render(args.mode, findings, usable_claims, hypotheses, state, args.persona, report),
        title=title,
        subtitle=subtitle,
        commands=commands,
        meta=meta,
        rules=rules,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
    print(f"доска собрана: {out} ({len(html_doc)} байт)")
    print(f"улик: {len(findings)}; утверждений: {len(usable_claims)}; версий: {len(hypotheses)}; "
          f"ошибок протокола: {len(report['errors'])}")
    return 0


def cmd_puzzle(args):
    puzzle, scenes = load_puzzle(args.puzzle)
    rules = selected_rules(args.rules, args.pack)
    result = solve(puzzle, scenes, rules, args.mode)
    if args.json:
        dump(result)
        return 0
    print(f"ЗАГАДКА: {result.get('title') or result.get('puzzle_id')}")
    if puzzle.get("text"):
        print(f"Условие: {puzzle['text']}")
    print("\nИзменения между кадрами:")
    for change in result["changes"]:
        print(f"  - {change['kind']}: {json.dumps({k: v for k, v in change.items() if k not in ('kind', 'id', 'between')}, ensure_ascii=False)}")
    print("\nУлики:")
    for finding in result["findings"]:
        print(f"  [{finding['rule_id']}] {finding['inference']} (≤ {finding['confidence_ceiling']:.2f}, "
              f"ступень: {finding.get('step', 'action')}, метки: {', '.join(finding['tags']) or '—'})")
    print("\nПрисутствовали:")
    for participant in result["participants"]:
        print(f"  {participant['label']}: {participant['score']:.2f} — {participant['explanation']}")
    report = validate(result["findings"], {"claims": result["claims"], "hypotheses": result["hypotheses"]})
    print("\n" + render(
        args.mode,
        result["findings"],
        result["claims"],
        result["hypotheses"],
        Verdict.SUFFICIENT if result["findings"] else Verdict.INSUFFICIENT,
        args.persona,
        report,
    ))
    if "evaluation" in result:
        evaluation = result["evaluation"]
        mark = "✓" if evaluation["correct"] else "✗"
        print(f"\n{mark} ожидался {evaluation['expected']}, получен {evaluation['predicted']}")
    return 0


def cmd_bench(args):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from run_eval import discover_benchmarks, run_benchmark
    benchmarks = discover_benchmarks(args.benchmarks)
    if not benchmarks:
        print("бенчмарки не найдены", file=sys.stderr)
        return 2
    failures = 0
    for name in benchmarks:
        report = run_benchmark(name, args.benchmarks)
        failures += report["failed_cases"]
        print(f"[{name}] случаев: {report['cases']}, провалено: {report['failed_cases']}, "
              f"цитаты: {report['citation_completeness']:.2f}, "
              f"калибровка (Brier): {report['brier']:.3f}")
        for case in report["case_results"]:
            status = "✓" if case["passed"] else "✗"
            print(f"   {status} {case['id']}: {case['detail']}")
    return 1 if failures else 0


def cmd_mcp_list(args):
    config = cfg.load_config(args.config)
    servers = config.get("mcp_servers", {})
    if not servers:
        print("MCP-серверы не настроены")
        return 0
    for name, spec in servers.items():
        print(f"{name}: {spec['command']} {' '.join(spec.get('args', []))}")
        for capability, tool in (spec.get("capability_map") or {}).items():
            print(f"    {capability} -> {tool}")
    return 0


def cmd_perceive(args):
    from .perception import MiniMaxPerception

    perception = MiniMaxPerception(model=args.model, think=args.think,
                                   votes=getattr(args, "votes", 1))
    scene, meta = perception.scene_graph(args.image, save_raw=args.raw)
    if args.out:
        Path(args.out).write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        dump(scene)
        return 0
    print(f"сцена-граф получен: {meta['model']}, {meta['latency_ms']} мс, вызовов: {meta.get('calls')}")
    print(f"  объектов: {len(scene['objects'])}, поверхностей: {len(scene['surfaces'])}, "
          f"регионов: {len(scene['regions'])}")
    for anomaly in scene["meta"]["perception"].get("anomalies", []):
        print(f"  ! {anomaly}")
    return 0


def cmd_analyze(args):
    from .perception import MiniMaxPerception

    apply_profile(args)

    perception = MiniMaxPerception(model=args.model, think=args.think,
                                   votes=getattr(args, "votes", 1))
    scene, meta = perception.scene_graph(args.image, save_raw=args.raw)
    rules = selected_rules(args.rules, args.pack)
    findings = evaluate_all(rules, scene)
    claims = build_claims(findings)
    report = validate(findings, {"claims": claims})
    usable = [c for c in claims
               if not any(e.get("claim_id") == c["claim_id"] for e in report["errors"])]
    hypotheses = score_hypotheses(findings, usable, [])
    state = decide_verdict(findings, usable, args.min_findings, args.mode)
    print(f"восприятие: {meta['model']}, {meta['latency_ms']} мс, вызовов: {meta.get('calls')}, "
          f"токенов: {meta.get('input_tokens')}→{meta.get('output_tokens')}")
    print(render(args.mode, findings, usable, hypotheses, state, args.persona, report))
    return 0


def cmd_reason(args):
    from .reasoning import MiniMaxReasoner

    apply_profile(args)

    scene = load_json(args.scene)
    rules = selected_rules(args.rules, args.pack)
    findings = evaluate_all(rules, scene)
    reasoner = MiniMaxReasoner(model=args.model, think=not args.no_think)
    ledger, meta = reasoner.reason(scene, findings, extra_instruction=args.instruction)
    report = validate(findings, ledger)
    usable = [c for c in ledger["claims"]
               if not any(e.get("claim_id") == c["claim_id"] for e in report["errors"])]
    hypotheses = score_hypotheses(findings, usable, ledger.get("hypotheses", []))
    state = decide_verdict(findings, usable, args.min_findings, args.mode)
    if args.out:
        Path(args.out).write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"рассуждение: {meta['model']}, {meta['latency_ms']} мс, вызовов: {meta.get('calls')}")
    if meta.get("dropped"):
        print(f"отброшено протоколом: {meta['dropped']}")
    print(render(args.mode, findings, usable, hypotheses, state, args.persona, report))
    return 0


def cmd_nextshot(args):
    from .nextshot import discriminator_questions, hypothesis_tags, kind_tags_from_rules, rank_questions

    apply_profile(args)

    scene = load_json(args.scene)
    rules = selected_rules(args.rules, args.pack)
    findings = evaluate_all(rules, scene)
    ledger = load_json(args.hypotheses) if args.hypotheses else {}
    claims = ledger.get("claims") or build_claims(findings)
    hypotheses = score_hypotheses(findings, claims, ledger.get("hypotheses", []))
    found_kinds = {r.get("kind") for r in scene.get("regions", [])}
    discriminators = discriminator_questions(hypotheses)[:args.limit]
    questions = rank_questions(
        hypotheses,
        hypothesis_tags(hypotheses, findings),
        kind_tags_from_rules(rules),
        found_kinds,
        limit=args.limit,
    )
    if args.json:
        dump({"discriminators": discriminators, "catalogue": questions})
        return 0
    if not discriminators and not questions:
        print("Спросить нечего: версий, которые можно различить, нет.")
        return 0
    if discriminators:
        print("Что разведут конкурирующие версии:")
        for index, question in enumerate(discriminators, start=1):
            print(f"\n{index}. {question['question']}")
            print(f"   зачем: {question['why']}")
            print(f"   затрагивает версий: {question['splits']} из {question['group']} "
                  f"({', '.join(question['hypotheses'])})")
    if questions:
        print("\nЧто снять дальше (по ценности информации):")
        for index, question in enumerate(questions, start=1):
            print(f"\n{index}. {question['question']}")
            print(f"   зачем: {question['why']}")
            print(f"   ценность информации: {question['eig']:.3f} бит; следы: {', '.join(question['kinds']) or '—'}")
    return 0


def cmd_session(args):
    from .dialog import Session

    apply_profile(args)

    rules = selected_rules(args.rules, args.pack)
    if args.state and Path(args.state).exists():
        session = Session.load(args.state, rules)
    else:
        participants = []
        if args.participants:
            participants = load_json(args.participants).get("participants", [])
        session = Session(rules, participants)

    for image in args.image or []:
        from .perception import MiniMaxPerception

        perception = MiniMaxPerception(model=args.model)
        scene, _ = perception.scene_graph(image)
        session.add_scene(scene, source=image)

    result = session.analyze()
    if args.state:
        session.save(args.state)

    if args.json:
        dump({
            "verdict": result["verdict"],
            "findings": [f["rule_id"] for f in result["findings"]],
            "claims": [c["claim_id"] for c in result["claims"]],
            "hypotheses": [h["text"] for h in result["hypotheses"]],
            "questions": result["questions"],
        })
        return 0

    print(f"раундов в сессии: {len(session.rounds)}; улик: {len(result['findings'])}; вердикт: {result['verdict']}")
    for finding in result["findings"]:
        print(f"  [{finding['rule_id']}] {finding['inference']} (≤ {finding['confidence_ceiling']:.2f})")
    if result["questions"]:
        print("\nЧто снять или уточнить дальше:")
        for question in result["questions"]:
            print(f"  • {question['question']}  (ценность {question['eig']:.3f} бит)")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="elementarno",
        description="Доказательный детектив по фото: улики, ссылки на правила, честный отказ.",
    )
    parser.add_argument("--config", default="config/profiles.json", help="файл профилей")
    parser.add_argument("--profile", help="идентификатор профиля")
    parser.add_argument("--rules", default=DEFAULT_RULES_DIR, help="каталог паков правил")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="структурная проверка сцены и правил")
    check.add_argument("scene")
    check.set_defaults(func=cmd_check)

    findings = sub.add_parser("findings", help="сработавшие правила и их цитаты")
    findings.add_argument("scene")
    findings.add_argument("--pack", action="append", help="ограничить паки (можно повторять)")
    findings.add_argument("--json", action="store_true")
    findings.add_argument("--profile", help="профиль из config/profiles.json")
    findings.set_defaults(func=cmd_findings)

    diff = sub.add_parser("diff", help="различия между двумя кадрами")
    diff.add_argument("before")
    diff.add_argument("after")
    diff.add_argument("--json", action="store_true")
    diff.set_defaults(func=cmd_diff)

    verify = sub.add_parser("verify", help="проверить ссылки утверждений")
    verify.add_argument("scene")
    verify.add_argument("--ledger", help="файл с утверждениями и гипотезами")
    verify.add_argument("--pack", action="append")
    verify.add_argument("--json", action="store_true")
    verify.add_argument("--profile", help="профиль из config/profiles.json")
    verify.set_defaults(func=cmd_verify)

    tell = sub.add_parser("tell", help="рассказать по сцене")
    tell.add_argument("scene")
    tell.add_argument("--ledger")
    tell.add_argument("--pack", action="append")
    tell.add_argument("--mode", default="detective", choices=["detective", "audit", "forensic", "solve", "nextshot"])
    tell.add_argument("--persona", default="plain", choices=["plain", "doyle", "forensic"])
    tell.add_argument("--min-findings", type=int, default=None,
                        help="сколько улик нужно для версии; флаг сильнее профиля")
    tell.add_argument("--profile", help="профиль из config/profiles.json")
    tell.set_defaults(func=cmd_tell)

    board = sub.add_parser("board", help="HTML-доска разбора: улики, нити, версии, переразбор")
    board.add_argument("scene")
    board.add_argument("--ledger", help="файл с утверждениями и гипотезами")
    board.add_argument("--out", default="board.html", help="куда записать страницу")
    board.add_argument("--pack", action="append")
    board.add_argument("--mode", default="detective", choices=["detective", "audit", "forensic"])
    board.add_argument("--persona", default="plain", choices=["plain", "doyle", "forensic"])
    board.add_argument("--title")
    board.add_argument("--subtitle")
    board.add_argument("--profile")
    board.set_defaults(func=cmd_board)

    puzzle = sub.add_parser("puzzle", help="разобрать загадку по серии кадров")
    puzzle.add_argument("puzzle")
    puzzle.add_argument("--pack", action="append")
    puzzle.add_argument("--mode", default="detective")
    puzzle.add_argument("--persona", default="doyle", choices=["plain", "doyle", "forensic"])
    puzzle.add_argument("--json", action="store_true")
    puzzle.add_argument("--profile", help="профиль из config/profiles.json")
    puzzle.set_defaults(func=cmd_puzzle)

    bench = sub.add_parser("bench", help="прогнать бенчмарки")
    bench.add_argument("--benchmarks", default="eval/benchmarks")
    bench.add_argument("--json", action="store_true")
    bench.set_defaults(func=cmd_bench)

    mcp = sub.add_parser("mcp-list", help="настроенные MCP-серверы")
    mcp.set_defaults(func=cmd_mcp_list)

    perceive = sub.add_parser("perceive", help="изображение → сцена-граф через мультимодальную модель")
    perceive.add_argument("image")
    perceive.add_argument("--model", default="MiniMax-M3")
    perceive.add_argument("--think", action="store_true", help="включить расширенное мышление")
    perceive.add_argument("--raw", help="куда сохранить сырой ответ модели")
    perceive.add_argument("--out", help="куда сохранить сцена-граф")
    perceive.add_argument("--votes", type=int, default=1,
                          help="сколько раз спросить перечисление следов: больше голосов — устойчивее")
    perceive.add_argument("--json", action="store_true")
    perceive.add_argument("--profile", help="профиль из config/profiles.json")
    perceive.set_defaults(func=cmd_perceive)

    analyze = sub.add_parser("analyze", help="изображение → улики → версия (всё сразу)")
    analyze.add_argument("image")
    analyze.add_argument("--model", default="MiniMax-M3")
    analyze.add_argument("--think", action="store_true")
    analyze.add_argument("--raw", help="куда сохранить сырой ответ модели")
    analyze.add_argument("--pack", action="append")
    analyze.add_argument("--mode", default="detective", choices=["detective", "audit", "forensic", "solve", "nextshot"])
    analyze.add_argument("--persona", default="doyle", choices=["plain", "doyle", "forensic"])
    analyze.add_argument("--min-findings", type=int, default=None,
                        help="сколько улик нужно для версии; флаг сильнее профиля")
    analyze.add_argument("--votes", type=int, default=1)
    analyze.add_argument("--profile", help="профиль из config/profiles.json")
    analyze.set_defaults(func=cmd_analyze)

    reason = sub.add_parser("reason", help="слой рассуждения: связать улики в утверждения и версии")
    reason.add_argument("scene")
    reason.add_argument("--model", default="MiniMax-M3")
    reason.add_argument("--no-think", action="store_true")
    reason.add_argument("--instruction", help="дополнительное условие от пользователя")
    reason.add_argument("--out", help="куда сохранить леджер")
    reason.add_argument("--pack", action="append")
    reason.add_argument("--mode", default="detective", choices=["detective", "audit", "forensic"])
    reason.add_argument("--persona", default="doyle", choices=["plain", "doyle", "forensic"])
    reason.add_argument("--min-findings", type=int, default=None,
                        help="сколько улик нужно для версии; флаг сильнее профиля")
    reason.add_argument("--profile", help="профиль из config/profiles.json")
    reason.set_defaults(func=cmd_reason)

    nextshot = sub.add_parser("nextshot", help="какой следующий кадр различит версии")
    nextshot.add_argument("scene")
    nextshot.add_argument("--hypotheses", help="файл с гипотезами")
    nextshot.add_argument("--pack", action="append")
    nextshot.add_argument("--limit", type=int, default=3)
    nextshot.add_argument("--json", action="store_true")
    nextshot.add_argument("--profile", help="профиль из config/profiles.json")
    nextshot.set_defaults(func=cmd_nextshot)

    session = sub.add_parser("session", help="серия фото: накопление улик и уточняющие вопросы")
    session.add_argument("--image", action="append", help="кадр для добавления (можно повторять)")
    session.add_argument("--state", help="файл состояния сессии")
    session.add_argument("--participants", help="файл со списком участников")
    session.add_argument("--model", default="MiniMax-M3")
    session.add_argument("--pack", action="append")
    session.add_argument("--json", action="store_true")
    session.add_argument("--profile", help="профиль из config/profiles.json")
    session.set_defaults(func=cmd_session)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
