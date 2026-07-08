// Empty PostCSS config, scoped to this project.
//
// Without this file, Vite's PostCSS resolver climbs parent directories
// looking for a config and can pick up an unrelated postcss.config.* from
// another project higher up the filesystem (e.g. one referencing
// @tailwindcss/postcss, which this project does not use/install). This
// file stops that climb so the build only ever depends on this repo.
export default {
  plugins: {},
}
