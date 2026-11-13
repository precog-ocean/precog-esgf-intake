# Contributing Guidelines

```
         5PO8$HHDBWWWWBBHK@UOPp                                                                                         
     !P&KWN0QQQQQQQ000QQQQQQ0NWHUGn                                                                                     
   FAHMQQQ0000000000000RR00000QQQ0D&g                                                                                   
 IbBQQ00000000000000Q0000R00000QXPAUY4gg4SShc  '2SVgggg4SSh%  ;pSdgggggggg>  +mS4ggggggu   7ghggggggSg7   Lghggggggggt  
jAQQR0000000000000Q0000RRR00000HnMQPezjz3QQN/  aQQG77zz3QQW+  jQQEo77777jj,  TQQELLLLLLx  <BQNnLLLnNQQI  %MQDuLj7777j>  
EQ0RRR0RRMNMMRRRRR00Q0Q000000RQ2ZQQ4T#ywEQQj  ,OQQVTJyJ4QQz  +$QQST#CCCCv   \HQD^         FQQj    *0Q4   gQQ1  "Lzzj)   
XWDDDHDBDWWNWBWBBDHKHDDDBHDDDWkJQQV}?1[1I*{-  TQQh}?!7QQW?-  fQQF{*}***}=   5QQj         lRQA`   ,OQR)  I0QZ   )aQQQ>   
fGK@KgEHdOK@K4GK@KkpV@$$Uq8@U$TORD| 1Fmw     |$0D/   |N0@_  )H00dppmmmmF+  xW0RVqhGPGz  -SQ0AmqPPXQ0F  _E00kmqGX400w    
IpgVqd44dd44ddd4d6qd44hmhd44gge*cv,|h4qC     =v)|    ;v><.  /v))%xx%xx%v.  "v))%x%%%%^  -v)>vxx%%%))'  'v))vxx%%%)>_    
 lLwy3yyJyyy#CyyywfyyyywfyyyyJyCJ#C3y#?                                                                                 
   t7jn#nTTnTnnnLTnLunnnjunnnnT#JTLje                                                                                   
     )zLLunTT#nTTTnnnTTTunT#TunuLL7                                                                                     
         ejojzLununnnnuuuuuLozz{    
```

Thank you for your interest in contributing to `precog-esgf-intake`.
Contributions are welcome, including bug reports, feature requests, code improvements, 
documentation updates, tests, and workflow examples.

## Ways to Contribute

There are several ways to contribute to this project:

1. **Report Bugs**  
   If you encounter a bug, please open an issue on
   the [issue tracker](https://github.com/precog-ocean/precog-esgf-intake/issues). Include a clear description of the
   problem, the ESGF search or download parameters used (if relevant), steps to reproduce the issue, and any useful
   logs, screenshots, or error messages.

2. **Suggest Enhancements**  
   If you have ideas for new features, improved workflow logic, additional validation checks, or support for new Earth
   system data use cases, please open an issue on
   the [issue tracker](https://github.com/precog-ocean/precog-esgf-intake/issues) describing the motivation and expected
   behavior.

3. **Submit Pull Requests**  
   If you would like to contribute code changes:
    - Fork the repository.
    - Create a dedicated branch for your changes.
    - Keep each pull request focused on a single feature, fix, or documentation update where possible.
    - Add or update tests under `tests/` when changing functionality.
    - Update `README.md` and notebooks if your change affects usage or workflow behavior.
    - Open a pull request against the main branch of the upstream
      repository: [precog-ocean/precog-esgf-intake](https://github.com/precog-ocean/precog-esgf-intake).

## Getting Started

To get started with local development:

1. Fork the upstream repository.
2. Clone your fork to your local machine.
3. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   
4. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

5. Check that the installation works:

    ```bash
    python3 tests/test_install.py
    ```

6. Make your changes and test them thoroughly.
7. Commit your changes with a clear and descriptive commit message.
8. Push your branch to your fork.
9. Open a pull request to the upstream repository.

## Code Style and Testing

 - Follow the existing module structure under `src/precog_esgf_intake/scripts` and `src/precog_esgf_intake/scripts/intake_esgf_mods`.
 - Keep modifications to upstream `intake-esgf` functionality clearly isolated and documented.
 - Where possible, add tests for new functionality and preserve reproducibility of existing workflows.
 - If a change affects user-facing behavior, update the documentation in `README.md` and any relevant example
notebooks.

## ESGF-Specific Issues

Because this software depends on distributed ESGF infrastructure, some failures may originate from remote archive
services rather than from the code itself. When reporting an issue, please include the relevant ESGF node, project,
experiment, variable, and grid combination where possible. This makes it easier to distinguish software bugs from
upstream archive-access problems.

## License

By contributing to this project, you agree that your contributions will be licensed under the GNU General Public License
v3.0.