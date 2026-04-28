"""
Sabu project
jug_lca_buildings package
lca_end_of_life_carbon module
Machine emission of different methods can be a default argument, because,
at this phase we use the average emission of different machines emission
for each part (demolition, onsite, recycling and landfilling).
If we are to use data for different processes, setters will be develop for
the machines of each process to replace the default arguments. In that sense,
a conditional will decide to use which value. The conditional will be defined
in the setters.
For next phases, we can use a Machine object to find the corresponding
emission.
Project Designer and Developer: Alireza Adli
Theoritical Support for LCA emissions: Mohammad Reza Seyedabadi
Licensed under the Apache License, Version 2.0.
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""


class EndOfLifeEmission:
  def __init__(
          self, recycling_ratio, onsite_recycling_ratio,
          company_recycling_ratio, landfilling_ratio,
          material_workload,
          demolition_machine_emission=4.3577325,
          onsite_machine_emission=2.0576313,
          companies_recycling_machine_emission=0.6189555,
          landfilling_machine_emission=15.7364044):
    self.recycling_ratio = recycling_ratio
    self.onsite_recycling_ratio = onsite_recycling_ratio
    self.company_recycling_ratio = company_recycling_ratio
    self.landfilling_ratio = landfilling_ratio
    self.material_workload = material_workload
    self.demolition_machine_emission = demolition_machine_emission
    self.onsite_machine_emission = onsite_machine_emission
    self.companies_recycling_machine_emission = \
        companies_recycling_machine_emission
    self.landfilling_machine_emission = landfilling_machine_emission

  def demolition(self):
    return self.demolition_machine_emission * self.material_workload

  def onsite_recycling(self):
    return self.recycling_ratio * (self.onsite_recycling_ratio *
                                   self.onsite_machine_emission *
                                   self.material_workload)

  def companies_recycling(self):
   return self.recycling_ratio * (self.company_recycling_ratio *
                                  self.companies_recycling_machine_emission *
                                  self.material_workload)

  def landfilling(self):
    return self.landfilling_ratio * \
           self.landfilling_machine_emission * \
           self.material_workload

  def calculate_end_of_life_emission(self):
    return self.demolition() + \
           self.onsite_recycling() + \
           self.companies_recycling() + \
           self.landfilling()
