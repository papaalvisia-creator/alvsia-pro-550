        seen.add(digest)
        try:
            # decompile_bytes already performs strict chunk parsing; the old
            # extra load_chunk call parsed the complete bytecode twice.
            decode_kwargs = {"deadline": deadline}
            if hybrid_long_string_size:
                decode_kwargs["hybrid_long_string_size"] = True
            try:
                source_text = decompile_bytes(memoryview(candidate), **decode_kwargs)
            except TypeError as exc:
                # Preserve compatibility with injected/test parser adapters that
                # still expose the pre-hybrid signature. Real hybrid parsing
                # remains enabled whenever the current parser accepts the flag.
                if "unexpected keyword argument 'hybrid_long_string_size'" not in str(exc):
                    raise
                source_text = decompile_bytes(memoryview(candidate), deadline=deadline)
            if not source_text or not source_text.strip():
                raise ValueError("decompiler returned empty source")
            ok, msg = validate_lua_source(source_text, expected_version="Lua 5.3")
            if not ok:
                raise ValueError(f"source validation failed: {msg}")
            final = Path(out_path)
            final.parent.mkdir(parents=True, exist_ok=True)
            final.write_text(source_text, encoding="utf-8")
            return True, f"decompiled_lua53 variant={variant} size={len(source_text)}"
        except TimeoutError as exc:
            return False, f"lua53_total_budget_exceeded_after_{budget_seconds:g}s: {exc}"
        except Exception as exc:
            return False, f"{variant}: {str(exc)[:320]}"

    ok, note = _try_candidate("standard", data)
    if ok:
        return True, note
    failures.append(note)