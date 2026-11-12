## IN SCOPE
- Searching other registered projects, named in the config, each in its own index with its own configuration
- Showing a link that could not be searched

## OUT OF SCOPE
- One merged ranking across projects
- Following a linked project's own links
- Projects on another machine, or not in the registry

## ADDED Requirements

### Requirement: A project can search linked projects in their own indexes

The configuration SHALL accept `linked`: a list of `{project, scope?, about?}` where `project` is
a name in the set-core project registry and `scope` is in the stored `<name>=<value>` form. A
search SHALL also run in each linked project's own index, with that project's own configuration
and the link's scope, and SHALL return each linked project's hits separately from this project's
hits, every one labelled with its project and a path relative to that project's root. A linked
project's own `linked` entries SHALL NOT be followed. Changing `linked` SHALL NOT force a re-index.
An entry without a project name, a duplicated name, a scope without `=`, or a non-string `about`
SHALL fail configuration loading, naming the offending key.

#### Scenario: A hit from a linked project
- **WHEN** project A links project B, and only B holds a section matching the query
- **THEN** A's own hits are empty, and B's block holds that section with `project` set to B and a path relative to B's root

#### Scenario: The link's scope
- **WHEN** the link carries `scope: "client=alfa"` and B holds matching sections under two client scopes
- **THEN** B's block holds only the `client=alfa` sections

#### Scenario: One level only
- **WHEN** B links a third project C, and only C holds a matching section
- **THEN** a search in A returns no hit from C

#### Scenario: Not part of the corpus
- **WHEN** two configurations differ only in `linked`
- **THEN** their corpus-config hashes are equal

### Requirement: A link that cannot be searched is shown

A linked project that cannot be searched (its name is not in the registry, its checkout is
missing, its configuration fails, or it is this project itself) SHALL appear on the page with
the reason, and the search SHALL still return this project's hits and every other linked
project's hits.

#### Scenario: An unregistered name
- **WHEN** A links `corpus` and `gone`, and `gone` is not in the registry
- **THEN** `corpus` is searched normally, and `gone` is reported as not searched with a reason naming the registry

#### Scenario: Linking itself
- **WHEN** A's `linked` names A's own registry entry
- **THEN** that link is reported as not searched, saying it is this project itself
