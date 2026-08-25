class SetLightingPower < OpenStudio::Measure::ModelMeasure
  def name
    'Set Lighting Power'
  end

  def description
    'Sets the installed lighting power density for the primary and secondary space groups.'
  end

  def modeler_description
    'The model carries two OS:Lights:Definition objects. They are told apart by a ' \
      'name pattern rather than by their current value, so the measure stays correct ' \
      'when applied repeatedly or in any order.'
  end

  def arguments(_model)
    args = OpenStudio::Measure::OSArgumentVector.new

    primary = OpenStudio::Measure::OSArgument.makeDoubleArgument('primary_w_m2', true)
    primary.setDisplayName('Primary lighting power density (W/m2)')
    primary.setDescription('Offices, conference hall, workshop.')
    primary.setDefaultValue(7.0)
    args << primary

    secondary = OpenStudio::Measure::OSArgument.makeDoubleArgument('secondary_w_m2', true)
    secondary.setDisplayName('Secondary lighting power density (W/m2)')
    secondary.setDescription('Corridors, stairs, service rooms, WC.')
    secondary.setDefaultValue(3.0)
    args << secondary

    pattern = OpenStudio::Measure::OSArgument.makeStringArgument('primary_name_pattern', true)
    pattern.setDisplayName('Name pattern identifying the primary definition')
    pattern.setDefaultValue('ofis')
    args << pattern

    args
  end

  def run(model, runner, user_arguments)
    super(model, runner, user_arguments)
    return false unless runner.validateUserArguments(arguments(model), user_arguments)

    primary_value = runner.getDoubleArgumentValue('primary_w_m2', user_arguments)
    secondary_value = runner.getDoubleArgumentValue('secondary_w_m2', user_arguments)
    pattern = runner.getStringArgumentValue('primary_name_pattern', user_arguments).downcase

    if primary_value <= 0 || secondary_value <= 0
      runner.registerError('Lighting power density must be greater than zero.')
      return false
    end

    definitions = model.getLightsDefinitions
    if definitions.empty?
      runner.registerError('No OS:Lights:Definition objects found.')
      return false
    end

    primary, secondary = definitions.partition do |definition|
      definition.nameString.downcase.include?(pattern)
    end

    if primary.empty?
      runner.registerError(
        "No lighting definition matched the pattern '#{pattern}'. " \
          "Available: #{definitions.map(&:nameString).join(', ')}"
      )
      return false
    end

    initial = definitions.map do |definition|
      value = definition.wattsperSpaceFloorArea
      "#{definition.nameString}=#{value.is_initialized ? value.get.round(2) : 'n/a'}"
    end

    applied = 0
    [[primary, primary_value], [secondary, secondary_value]].each do |group, value|
      group.each do |definition|
        # Tanim W/m2 disinda bir yontem kullaniyorsa sessizce degistirmek yerine
        # atlanir; aksi halde toplam guc beklenmedik sekilde degisir.
        unless definition.wattsperSpaceFloorArea.is_initialized
          runner.registerWarning(
            "#{definition.nameString} does not use Watts/Area; left unchanged."
          )
          next
        end
        definition.setWattsperSpaceFloorArea(value)
        applied += 1
      end
    end

    runner.registerInitialCondition(initial.join('; '))
    runner.registerValue('lighting_primary_w_m2', primary_value, 'W/m2')
    runner.registerValue('lighting_secondary_w_m2', secondary_value, 'W/m2')
    runner.registerFinalCondition(
      "Updated #{applied} lighting definition(s): #{primary.length} primary at " \
        "#{primary_value} W/m2, #{secondary.length} secondary at #{secondary_value} W/m2."
    )
    true
  rescue StandardError => e
    runner.registerError("Set Lighting Power failed: #{e.message}")
    false
  end
end

SetLightingPower.new.registerWithApplication
