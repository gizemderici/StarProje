class SetEpsThickness < OpenStudio::Measure::ModelMeasure
  def name
    'Set EPS Thickness'
  end

  def description
    'Changes the EPS layer of a named opaque construction before simulation.'
  end

  def modeler_description
    'Edits the target construction in place so explicit surface assignments and default construction sets keep referencing the changed construction.'
  end

  def arguments(_model)
    args = OpenStudio::Measure::OSArgumentVector.new

    target = OpenStudio::Measure::OSArgument.makeStringArgument('target_construction', true)
    target.setDisplayName('Target construction')
    target.setDefaultValue('duvr_std_eps')
    args << target

    thickness = OpenStudio::Measure::OSArgument.makeDoubleArgument('eps_thickness_cm', true)
    thickness.setDisplayName('EPS thickness (cm)')
    thickness.setDefaultValue(10.0)
    args << thickness

    conductivity = OpenStudio::Measure::OSArgument.makeDoubleArgument('conductivity_w_mk', true)
    conductivity.setDisplayName('EPS conductivity (W/m-K)')
    conductivity.setDefaultValue(0.039)
    args << conductivity

    density = OpenStudio::Measure::OSArgument.makeDoubleArgument('density_kg_m3', true)
    density.setDisplayName('EPS density (kg/m3)')
    density.setDefaultValue(16.0)
    args << density

    specific_heat = OpenStudio::Measure::OSArgument.makeDoubleArgument('specific_heat_j_kgk', true)
    specific_heat.setDisplayName('EPS specific heat (J/kg-K)')
    specific_heat.setDefaultValue(1250.0)
    args << specific_heat

    args
  end

  def run(model, runner, user_arguments)
    super(model, runner, user_arguments)
    return false unless runner.validateUserArguments(arguments(model), user_arguments)

    target_name = runner.getStringArgumentValue('target_construction', user_arguments)
    thickness_cm = runner.getDoubleArgumentValue('eps_thickness_cm', user_arguments)
    conductivity = runner.getDoubleArgumentValue('conductivity_w_mk', user_arguments)
    density = runner.getDoubleArgumentValue('density_kg_m3', user_arguments)
    specific_heat = runner.getDoubleArgumentValue('specific_heat_j_kgk', user_arguments)

    if thickness_cm <= 0 || conductivity <= 0 || density <= 0 || specific_heat <= 0
      runner.registerError('EPS physical properties must be greater than zero.')
      return false
    end

    construction = model.getConstructions.find { |item| item.nameString == target_name }
    unless construction
      runner.registerError("Construction not found: #{target_name}")
      return false
    end

    layers = construction.layers.to_a
    eps_indices = layers.each_index.select { |index| layers[index].nameString.downcase.include?('eps') }
    if eps_indices.empty?
      runner.registerError("No EPS layer was found in construction: #{target_name}")
      return false
    end

    eps = OpenStudio::Model::StandardOpaqueMaterial.new(model)
    eps.setName(format('eps %.2f cm', thickness_cm))
    eps.setRoughness('MediumSmooth')
    eps.setThickness(thickness_cm / 100.0)
    eps.setConductivity(conductivity)
    eps.setDensity(density)
    eps.setSpecificHeat(specific_heat)

    eps_indices.each { |index| layers[index] = eps }
    construction.setLayers(layers)
    construction.setName(format('%s_alt_%gcm', target_name, thickness_cm))

    runner.registerValue('eps_thickness_cm', thickness_cm, 'cm')
    runner.registerValue('eps_conductivity_w_mk', conductivity, 'W/m-K')
    runner.registerFinalCondition(
      "Updated #{eps_indices.length} EPS layer(s) in #{target_name}; all existing references remain connected."
    )
    true
  rescue StandardError => e
    runner.registerError("Set EPS Thickness failed: #{e.message}")
    false
  end
end

SetEpsThickness.new.registerWithApplication
