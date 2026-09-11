import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_smiles_parsing(selenium):
    from rdkit import Chem

    mol = Chem.MolFromSmiles("CCO")
    assert mol is not None
    assert mol.GetNumAtoms() == 3
    assert mol.GetNumBonds() == 2

    # Canonical SMILES
    assert Chem.MolToSmiles(Chem.MolFromSmiles("OCC")) == "CCO"

    # Aromatic molecules
    benzene = Chem.MolFromSmiles("c1ccccc1")
    assert benzene is not None
    assert benzene.GetNumAtoms() == 6


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_substructure_search(selenium):
    from rdkit import Chem

    mol = Chem.MolFromSmiles("CCO")
    benzene = Chem.MolFromSmiles("c1ccccc1")
    pat = Chem.MolFromSmarts("[OH]")
    assert mol.HasSubstructMatch(pat)
    assert not benzene.HasSubstructMatch(pat)


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_inchi(selenium):
    from rdkit import Chem
    from rdkit.Chem import inchi

    mol = Chem.MolFromSmiles("CCO")
    inchi_str = inchi.MolToInchi(mol)
    assert inchi_str.startswith("InChI=")

    # Roundtrip
    mol2 = inchi.MolFromInchi(inchi_str)
    assert Chem.MolToSmiles(mol2) == "CCO"


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_molblock_roundtrip(selenium):
    from rdkit import Chem

    aspirin = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
    molblock = Chem.MolToMolBlock(aspirin)
    assert "V2000" in molblock
    aspirin2 = Chem.MolFromMolBlock(molblock)
    assert Chem.MolToSmiles(aspirin) == Chem.MolToSmiles(aspirin2)


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_ring_info(selenium):
    from rdkit import Chem

    benzene = Chem.MolFromSmiles("c1ccccc1")
    ri = benzene.GetRingInfo()
    assert ri.NumRings() == 1


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_atom_bond_properties(selenium):
    from rdkit import Chem

    mol = Chem.MolFromSmiles("CCO")
    atom = mol.GetAtomWithIdx(2)
    assert atom.GetSymbol() == "O"
    assert atom.GetAtomicNum() == 8
    bond = mol.GetBondWithIdx(1)
    assert bond.GetBondTypeAsDouble() == 1.0


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_molecular_formula(selenium):
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors

    aspirin = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
    assert rdMolDescriptors.CalcMolFormula(aspirin) == "C9H8O4"


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_chemical_reactions(selenium):
    from rdkit.Chem import AllChem

    rxn = AllChem.ReactionFromSmarts("[C:1](=O)[OH].[N:2]>>[C:1](=O)[N:2]")
    assert rxn is not None


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_2d_coords_and_svg(selenium):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from rdkit.Chem.Draw import rdMolDraw2D

    benzene = Chem.MolFromSmiles("c1ccccc1")
    AllChem.Compute2DCoords(benzene)
    conf = benzene.GetConformer()
    pos = conf.GetAtomPosition(0)
    assert not (pos.x == 0.0 and pos.y == 0.0)

    # SVG drawing
    drawer = rdMolDraw2D.MolDraw2DSVG(300, 300)
    drawer.DrawMolecule(benzene)
    drawer.FinishDrawing()
    svg = drawer.GetDrawingText()
    assert "<svg" in svg and "</svg>" in svg


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_drug_molecules(selenium):
    from rdkit import Chem

    drugs = {
        "caffeine": "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
        "ibuprofen": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
        "penicillin_G": "CC1(C)SC2C(NC(=O)Cc3ccccc3)C(=O)N2C1C(=O)O",
    }
    for name, smi in drugs.items():
        m = Chem.MolFromSmiles(smi)
        assert m is not None, f"Failed to parse {name}"
        can = Chem.MolToSmiles(m)
        m2 = Chem.MolFromSmiles(can)
        assert Chem.MolToSmiles(m2) == can


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_binary_serialization(selenium):
    from rdkit import Chem

    aspirin = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
    aspirin_bin = aspirin.ToBinary()
    assert len(aspirin_bin) > 0
    aspirin2 = Chem.Mol(aspirin_bin)
    assert Chem.MolToSmiles(aspirin2) == Chem.MolToSmiles(aspirin)


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_fingerprint_numpy(selenium):
    import numpy as np
    from rdkit import Chem
    from rdkit.Chem import rdFingerprintGenerator

    mol = Chem.MolFromSmiles("CCO")
    fpgen = rdFingerprintGenerator.GetMorganGenerator(radius=2)
    fp_np = fpgen.GetFingerprintAsNumPy(mol)
    assert isinstance(fp_np, np.ndarray)
    assert fp_np.shape[0] > 0


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_3d_embedding_and_optimization(selenium):
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors3D

    # 3D embedding
    mol = Chem.MolFromSmiles("c1ccc(O)cc1")
    mol = Chem.AddHs(mol)
    res = AllChem.EmbedMolecule(mol, randomSeed=42)
    assert res == 0
    conf = mol.GetConformer()
    assert conf.Is3D()

    # UFF optimization
    res_opt = AllChem.UFFOptimizeMolecule(mol, maxIters=200)
    assert res_opt == 0

    # 3D descriptors
    butane = Chem.MolFromSmiles("CCCC")
    butane = Chem.AddHs(butane)
    AllChem.EmbedMolecule(butane, randomSeed=42)
    asphericity = Descriptors3D.Asphericity(butane)
    assert asphericity >= 0


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_add_remove_hydrogens(selenium):
    from rdkit import Chem

    phenol = Chem.MolFromSmiles("c1ccc(O)cc1")
    assert phenol.GetNumAtoms() == 7
    phenol_h = Chem.AddHs(phenol)
    assert phenol_h.GetNumAtoms() == 13
    phenol_noh = Chem.RemoveHs(phenol_h)
    assert phenol_noh.GetNumAtoms() == 7
    assert Chem.MolToSmiles(phenol) == Chem.MolToSmiles(phenol_noh)


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_kekulization(selenium):
    from rdkit import Chem

    arom = Chem.MolFromSmiles("c1ccccc1")
    bond = arom.GetBondWithIdx(0)
    assert bond.GetIsAromatic()
    assert bond.GetBondType() == Chem.rdchem.BondType.AROMATIC

    Chem.Kekulize(arom, clearAromaticFlags=True)
    bond_k = arom.GetBondWithIdx(0)
    assert not bond_k.GetIsAromatic()
    assert bond_k.GetBondType() in (
        Chem.rdchem.BondType.SINGLE,
        Chem.rdchem.BondType.DOUBLE,
    )
    kek_smi = Chem.MolToSmiles(arom, kekuleSmiles=True)
    assert "c" not in kek_smi


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_mmff_optimization(selenium):
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol = Chem.MolFromSmiles("c1ccc(O)cc1")
    mol = Chem.AddHs(mol)
    AllChem.EmbedMolecule(mol, randomSeed=42)
    props = AllChem.MMFFGetMoleculeProperties(mol)
    assert props is not None
    ff = AllChem.MMFFGetMoleculeForceField(mol, props)
    assert ff is not None
    e_before = ff.CalcEnergy()
    res = AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
    assert res == 0
    ff2 = AllChem.MMFFGetMoleculeForceField(
        mol, AllChem.MMFFGetMoleculeProperties(mol)
    )
    e_after = ff2.CalcEnergy()
    assert e_after <= e_before


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_multiple_conformers(selenium):
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol = Chem.MolFromSmiles("CCCCCCC")
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = 42
    params.numThreads = 1
    cids = AllChem.EmbedMultipleConfs(mol, numConfs=5, params=params)
    assert len(cids) == 5
    assert mol.GetNumConformers() == 5


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_molecular_alignment(selenium):
    from rdkit import Chem
    from rdkit.Chem import AllChem, rdMolAlign

    mol = Chem.MolFromSmiles("CCCCCCC")
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = 42
    params.numThreads = 1
    AllChem.EmbedMultipleConfs(mol, numConfs=3, params=params)
    rmsds = []
    rdMolAlign.AlignMolConformers(mol, RMSlist=rmsds)
    assert len(rmsds) > 0

    # Align two molecules
    ref = Chem.AddHs(Chem.MolFromSmiles("c1ccccc1O"))
    AllChem.EmbedMolecule(ref, randomSeed=42)
    probe = Chem.AddHs(Chem.MolFromSmiles("c1ccccc1O"))
    AllChem.EmbedMolecule(probe, randomSeed=123)
    rmsd = rdMolAlign.AlignMol(probe, ref)
    assert rmsd >= 0


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_mcs(selenium):
    from rdkit import Chem
    from rdkit.Chem import rdFMCS

    mol_a = Chem.MolFromSmiles("c1ccccc1CCO")
    mol_b = Chem.MolFromSmiles("c1ccccc1CCCO")
    mcs = rdFMCS.FindMCS([mol_a, mol_b])
    assert mcs.numAtoms > 0
    assert mcs.numBonds > 0


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_tautomer_enumeration(selenium):
    from rdkit import Chem
    from rdkit.Chem.MolStandardize import rdMolStandardize

    taut_enum = rdMolStandardize.TautomerEnumerator()
    keto = Chem.MolFromSmiles("OC1=CC=CC=C1")
    canonical = taut_enum.Canonicalize(keto)
    assert canonical is not None
    tautomers = list(taut_enum.Enumerate(keto))
    assert len(tautomers) >= 1


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_salt_removal(selenium):
    from rdkit import Chem
    from rdkit.Chem.SaltRemover import SaltRemover

    remover = SaltRemover()
    salt_mol = Chem.MolFromSmiles("[Na+].OC1=CC=CC=C1")
    stripped = remover.StripMol(salt_mol)
    assert stripped is not None
    assert stripped.GetNumAtoms() < salt_mol.GetNumAtoms()


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_stereochemistry(selenium):
    from rdkit import Chem
    from rdkit.Chem import AllChem

    chiral = Chem.MolFromSmiles("C[C@@H](O)F")
    Chem.AssignStereochemistry(chiral, cleanIt=True, force=True)
    stereo_atom = chiral.GetAtomWithIdx(1)
    assert stereo_atom.GetChiralTag() != Chem.rdchem.ChiralType.CHI_UNSPECIFIED

    # AssignStereochemistryFrom3D
    mol_3d = Chem.AddHs(Chem.MolFromSmiles("C[C@@H](O)F"))
    AllChem.EmbedMolecule(mol_3d, randomSeed=42)
    Chem.AssignStereochemistryFrom3D(mol_3d)


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_rwmol_and_combine(selenium):
    from rdkit import Chem

    rwmol = Chem.RWMol(Chem.MolFromSmiles("C"))
    idx = rwmol.AddAtom(Chem.Atom(8))
    rwmol.AddBond(0, idx, Chem.rdchem.BondType.SINGLE)
    Chem.SanitizeMol(rwmol)
    assert Chem.MolToSmiles(rwmol) == "CO"

    combined = Chem.CombineMols(Chem.MolFromSmiles("C"), Chem.MolFromSmiles("O"))
    assert combined.GetNumAtoms() == 2


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_descriptors(selenium):
    from rdkit import Chem
    from rdkit.Chem import Descriptors

    aspirin = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
    assert len(Descriptors.descList) > 0
    mw = Descriptors.MolWt(aspirin)
    assert 170 < mw < 190
    logp = Descriptors.MolLogP(aspirin)
    assert isinstance(logp, float)


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_maccs_fingerprints(selenium):
    from rdkit import Chem
    from rdkit.Chem import MACCSkeys

    aspirin = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
    maccs = MACCSkeys.GenMACCSKeys(aspirin)
    assert maccs is not None
    assert maccs.GetNumOnBits() > 0


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_sdf_read_write(selenium):
    from rdkit import Chem

    aspirin = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
    benzene = Chem.MolFromSmiles("c1ccccc1")

    sdf_out = Chem.SDWriter("/tmp/test.sdf")
    sdf_out.write(aspirin)
    sdf_out.write(benzene)
    sdf_out.close()

    suppl = Chem.SDMolSupplier("/tmp/test.sdf")
    mols = [m for m in suppl if m is not None]
    assert len(mols) == 2
    assert Chem.MolToSmiles(mols[0]) == Chem.MolToSmiles(aspirin)


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_data_dir_and_chemical_features(selenium):
    import os
    from rdkit import RDConfig, Chem
    from rdkit.Chem import AllChem, ChemicalFeatures

    assert os.path.isdir(RDConfig.RDDataDir)
    fdef_path = os.path.join(RDConfig.RDDataDir, "BaseFeatures.fdef")
    assert os.path.isfile(fdef_path)

    feat_factory = ChemicalFeatures.BuildFeatureFactory(fdef_path)
    assert feat_factory is not None

    aspirin = Chem.AddHs(Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O"))
    AllChem.EmbedMolecule(aspirin, randomSeed=42)
    feats = feat_factory.GetFeaturesForMol(aspirin)
    assert len(feats) > 0


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_coordgen_2d_coords(selenium):
    from rdkit import Chem
    from rdkit.Chem import rdCoordGen, AllChem

    mol = Chem.MolFromSmiles("c1ccc2c(c1)cc1ccc3cccc4ccc2c1c34")  # pyrene
    rdCoordGen.AddCoords(mol)
    conf = mol.GetConformer()
    assert conf.GetNumAtoms() == mol.GetNumAtoms()

    # Verify coordinates are non-degenerate (not all at origin)
    positions = [conf.GetAtomPosition(i) for i in range(mol.GetNumAtoms())]
    xs = [p.x for p in positions]
    ys = [p.y for p in positions]
    assert max(xs) - min(xs) > 0.1
    assert max(ys) - min(ys) > 0.1


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["rdkit"])
def test_chemdraw(selenium):
    from rdkit import Chem
    from rdkit.Chem import AllChem, rdChemDraw

    # Generate 2D coords (needed for ChemDraw output)
    mol = Chem.MolFromSmiles("c1ccccc1O")
    AllChem.Compute2DCoords(mol)

    # Write to ChemDraw format and read back
    cdx = rdChemDraw.MolToChemDrawBlock(mol)
    assert len(cdx) > 0

    mols = rdChemDraw.MolsFromChemDrawBlock(cdx)
    assert len(mols) >= 1
    assert mols[0].GetNumAtoms() == mol.GetNumAtoms()
