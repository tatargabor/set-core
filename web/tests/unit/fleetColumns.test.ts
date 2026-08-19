import { describe, expect, it } from 'vitest'
import { COLUMN_CHOICES, DEFAULT_COLUMNS, resolveColumns } from '../../src/lib/fleetViewState'

describe('a projektenkénti oszlopszám', () => {
  it('kettő, amíg nincs döntés — ezt kérte a felhasználó', () => {
    expect(resolveColumns({})).toBe(2)
    expect(DEFAULT_COLUMNS).toBe(2)
  })

  it('a megjegyzett választás felülírja az alapértelmezést', () => {
    for (const c of COLUMN_CHOICES) expect(resolveColumns({ columns: c })).toBe(c)
  })

  it('az EGY oszlop is választás, nem hiány', () => {
    // A megkülönböztetés ugyanaz, mint az `enlarged`-nél: aki egy oszlopot
    // választott, annak nem szabad kettőt kapnia csak azért, mert az az
    // alapértelmezés. Egy `?? DEFAULT` alapú megvalósítás ezen nem bukna el,
    // ha 1 hamis értéknek számítana — ezért van itt külön.
    expect(resolveColumns({ columns: 1 })).toBe(1)
  })

  it('a tartományon kívüli tárolt érték az ALAPÉRTELMEZÉSRE esik vissza, nem a legközelebbire', () => {
    // Kézzel szerkesztett vagy régi tárolt érték nem preferencia, hanem
    // sérülés. A "legközelebbi értelmes" tippelés azt állítaná, hogy tudjuk,
    // mit akart — nem tudjuk.
    for (const bad of [0, -1, 5, 99, 2.5, Number.NaN]) {
      expect(resolveColumns({ columns: bad })).toBe(DEFAULT_COLUMNS)
    }
  })

  it('a nem szám típusú tárolt érték sem dönt el semmit', () => {
    for (const bad of ['2', null, {}, []] as unknown[]) {
      expect(resolveColumns({ columns: bad as number })).toBe(DEFAULT_COLUMNS)
    }
  })
})
