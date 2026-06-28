abi <abi/4.0>,
include <tunables/global>

profile kobe-ai /opt/Open\ Generative\ AI/kobe-ai flags=(unconfined) {
  userns,
  include if exists <local/kobe-ai>
}
