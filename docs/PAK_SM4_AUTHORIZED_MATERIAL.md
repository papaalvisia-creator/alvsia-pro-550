# Authorized PAK SM4 material

ALVSIA never embeds game/server SM4 material in the shipped source.

## Runtime file

Set `ALVSIA_SM4_MATERIAL_FILE` to a local JSON file containing either:

```json
{
  "method_keys": {
    "53": "<authorized-material>"
  }
}
```

or the legacy ordered candidate form:

```json
{
  "candidates": ["<authorized-candidate>"]
}
```

Only authorized caller-supplied material is accepted. Values are never logged.

## Reference PAK 4.7.0.21756

The two currently blocked entries both use encryption method `53`:

- `Config/DefaultEngineRedirects_BLUEHOLE.ini`
- `Config/DefaultEngineRedirects_JAPANKOREA.ini`

Therefore the reference gate needs only the authorized material for method 53; it does not need unrelated method keys.

For CI, store the JSON object as the repository Actions secret `REFERENCE_PAK_SM4_MATERIAL`. The reference-corpus workflow writes it only to the ephemeral runner filesystem and exposes it through `ALVSIA_SM4_MATERIAL_FILE`.

Never commit the actual material, paste it into logs, or place it in APK/source assets.